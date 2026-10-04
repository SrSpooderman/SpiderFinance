import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from openpyxl import Workbook
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import TransactionIn
from app.application.finance import account_balances, get_account, validate_transaction
from app.application.importing import MAX_FILE_BYTES, PORTABLE_FIELDS, parse_file, parse_row, unescape_spreadsheet
from app.infrastructure.models import Account, Category, ImportJob, ImportKey, ImportRow, InvestmentPosition, Transaction, User

router = APIRouter(tags=["imports"])
FIELDS = {
    "date", "concept", "amount", "type", "account_id", "source_account_id",
    "destination_account_id", "category_id", "source_account", "destination_account",
    "category", "status", "notes", "payment_method", "is_fixed", "is_necessary", "external_id",
}
EXPORT_FIELDS = PORTABLE_FIELDS


def account_label(account: Account) -> str:
    return f"{account.name} [{account.currency}]"


def category_label(category: Category, by_id: dict[int, Category]) -> str:
    return f"{by_id[category.parent_id].name} / {category.name}" if category.parent_id else category.name


def reference_index(db: DbSession, user_id: int):
    accounts = list(db.scalars(select(Account).where(Account.user_id == user_id)))
    categories = list(db.scalars(select(Category).where(Category.user_id == user_id)))
    accounts_by_id = {item.id: item for item in accounts}
    categories_by_id = {item.id: item for item in categories}
    account_refs: dict[str, set[int]] = {}
    category_refs: dict[str, set[int]] = {}
    for item in accounts:
        account_refs.setdefault(account_label(item), set()).add(item.id)
    for item in accounts:
        account_refs.setdefault(item.name, set()).add(item.id)
    for item in categories:
        category_refs.setdefault(category_label(item, categories_by_id), set()).add(item.id)
    for item in categories:
        if item.parent_id is not None:
            category_refs.setdefault(item.name, set()).add(item.id)
    return accounts_by_id, categories_by_id, account_refs, category_refs


def resolve_reference(value: str, references: dict[str, set[int]], kind: str) -> int:
    candidates = references.get(value, set())
    if not candidates:
        raise ValueError(f"{kind} no encontrada: {value}. Créala antes de importar o corrige el archivo")
    if len(candidates) != 1:
        raise ValueError(f"{kind} ambigua: {value}. Usa un nombre único en la instancia de destino")
    return next(iter(candidates))


class PreviewIn(BaseModel):
    sheet_name: str
    mapping: dict[str, str]
    default_account_id: int | None = None
    positive_is_income: bool = True


class ImportRowOut(BaseModel):
    row_number: int
    raw: dict
    parsed: dict | None
    error: str | None
    status: str


class ImportJobOut(BaseModel):
    id: int
    filename: str
    sheet_names: list[str]
    selected_sheet: str | None
    headers: list[str]
    mapping: dict[str, str]
    default_account_id: int | None
    positive_is_income: bool
    status: str
    total_rows: int
    imported_rows: int
    skipped_rows: int
    error_rows: int
    rows: list[ImportRowOut]


def owned_job(db: DbSession, user_id: int, job_id: int) -> ImportJob:
    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user_id))
    if job is None:
        raise HTTPException(404, "Importación no encontrada")
    return job


def job_out(db: DbSession, job: ImportJob, include_rows: bool = True) -> ImportJobOut:
    rows = db.scalars(select(ImportRow).where(
        ImportRow.job_id == job.id, ImportRow.sheet_name == job.selected_sheet
    ).order_by(ImportRow.row_number).limit(100)).all() if include_rows else []
    return ImportJobOut(
        id=job.id, filename=job.filename, sheet_names=job.sheet_names,
        selected_sheet=job.selected_sheet, headers=job.headers, mapping=job.mapping,
        default_account_id=job.default_account_id, positive_is_income=job.positive_is_income,
        status=job.status, total_rows=job.total_rows, imported_rows=job.imported_rows,
        skipped_rows=job.skipped_rows, error_rows=job.error_rows,
        rows=[ImportRowOut(
            row_number=row.row_number, raw=row.raw, parsed=row.parsed,
            error=row.error, status=row.status,
        ) for row in rows],
    )


@router.get("/imports", response_model=list[ImportJobOut])
def list_jobs(user: CurrentUser, db: DbSession):
    jobs = db.scalars(select(ImportJob).where(ImportJob.user_id == user.id).order_by(ImportJob.id.desc()).limit(20)).all()
    return [job_out(db, job, include_rows=False) for job in jobs]


@router.get("/imports/{job_id}", response_model=ImportJobOut)
def read_job(job_id: int, user: CurrentUser, db: DbSession):
    return job_out(db, owned_job(db, user.id, job_id))


@router.delete("/imports/{job_id}", status_code=204)
def delete_job(job_id: int, user: CurrentUser, db: DbSession):
    job = owned_job(db, user.id, job_id)
    rows = db.scalars(select(ImportRow).where(ImportRow.job_id == job.id)).all()
    for row in rows:
        db.delete(row)
    db.delete(job)
    db.commit()


@router.get("/imports/{job_id}/sheets", response_model=dict[str, list[str]])
def read_sheet_headers(job_id: int, user: CurrentUser, db: DbSession):
    job = owned_job(db, user.id, job_id)
    result = {}
    for name in job.sheet_names:
        row = db.scalar(select(ImportRow).where(
            ImportRow.job_id == job.id, ImportRow.sheet_name == name
        ).order_by(ImportRow.row_number).limit(1))
        result[name] = list(row.raw) if row else (job.headers if name == job.selected_sheet else [])
    return result


@router.post("/imports", response_model=ImportJobOut, status_code=201)
async def upload_import(user: CurrentUser, db: DbSession, file: UploadFile = File(...)):
    filename = Path(file.filename or "archivo").name[:255]
    contents = await file.read(MAX_FILE_BYTES + 1)
    try:
        sheets = parse_file(contents, filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    selected = next(iter(sheets))
    job = ImportJob(
        user_id=user.id, filename=filename, file_type=Path(filename).suffix.lower().lstrip("."),
        sheet_names=list(sheets), selected_sheet=selected, headers=sheets[selected][0],
        mapping={}, default_account_id=None, positive_is_income=True,
        status="UPLOADED", total_rows=len(sheets[selected][1]), imported_rows=0,
        skipped_rows=0, error_rows=0,
    )
    db.add(job)
    db.flush()
    for sheet_name, (_, rows) in sheets.items():
        db.add_all(ImportRow(
            user_id=user.id, job_id=job.id, sheet_name=sheet_name, row_number=number,
            raw=raw, parsed=None, error=None, dedup_key=None, status="UPLOADED",
        ) for number, raw in rows)
    db.commit()
    db.refresh(job)
    return job_out(db, job)


@router.post("/imports/{job_id}/preview", response_model=ImportJobOut)
def preview_import(job_id: int, data: PreviewIn, user: CurrentUser, db: DbSession):
    job = owned_job(db, user.id, job_id)
    if job.status == "CONFIRMED":
        raise HTTPException(409, "La importación ya se confirmó")
    if data.sheet_name not in job.sheet_names:
        raise HTTPException(422, "Hoja no encontrada")
    rows = list(db.scalars(select(ImportRow).where(
        ImportRow.job_id == job.id, ImportRow.sheet_name == data.sheet_name
    ).order_by(ImportRow.row_number)))
    headers = list(rows[0].raw) if rows else job.headers if data.sheet_name == job.selected_sheet else []
    if any(key not in FIELDS or value not in headers for key, value in data.mapping.items()):
        raise HTTPException(422, "El mapeo contiene campos o columnas desconocidos")
    if any(field not in data.mapping for field in ("date", "concept", "amount")):
        raise HTTPException(422, "Asigna fecha, concepto e importe")
    if data.default_account_id is not None:
        get_account(db, user.id, data.default_account_id)
    job.selected_sheet = data.sheet_name
    job.headers = headers
    job.mapping = data.mapping
    job.default_account_id = data.default_account_id
    job.positive_is_income = data.positive_is_income
    job.total_rows = len(rows)
    job.imported_rows = 0
    job.status = "PREVIEWED"
    _, _, account_refs, category_refs = reference_index(db, user.id)
    spreadsheet_safe = job.file_type in ("csv", "xlsx")
    occurrences: dict[str, int] = {}
    keys = []
    for row in rows:
        row.parsed = None
        row.error = None
        row.dedup_key = None
        try:
            raw_data = parse_row(row.raw, data.mapping, data.default_account_id,
                                 data.positive_is_income, spreadsheet_safe)
            for field, target in (("source_account", "source_account_id"),
                                  ("destination_account", "destination_account_id")):
                value = row.raw.get(data.mapping.get(field, ""), "").strip()
                if value:
                    if spreadsheet_safe:
                        value = unescape_spreadsheet(value)
                    raw_data[target] = resolve_reference(value, account_refs, "Cuenta")
            value = row.raw.get(data.mapping.get("category", ""), "").strip()
            if value:
                if spreadsheet_safe:
                    value = unescape_spreadsheet(value)
                raw_data["category_id"] = resolve_reference(value, category_refs, "Categoría")
            parsed = TransactionIn.model_validate(raw_data)
            values = parsed.model_dump()
            validate_transaction(db, user.id, values)
            normalized = parsed.model_dump(mode="json")
            external = row.raw.get(data.mapping.get("external_id", ""), "")
            if external:
                fingerprint = json.dumps(
                    {"account": normalized.get("source_account_id") or normalized.get("destination_account_id"),
                     "external": str(external)},
                    sort_keys=True, ensure_ascii=False,
                )
            else:
                fingerprint = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
                occurrences[fingerprint] = occurrences.get(fingerprint, 0) + 1
                fingerprint += f":{occurrences[fingerprint]}"
            row.dedup_key = hashlib.sha256(fingerprint.encode()).hexdigest()
            row.parsed = normalized
            row.status = "READY"
            keys.append(row.dedup_key)
        except (ValueError, ValidationError, HTTPException) as exc:
            row.error = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
            row.status = "ERROR"
    existing = set(db.scalars(select(ImportKey.key).where(
        ImportKey.user_id == user.id, ImportKey.key.in_(keys)
    ))) if keys else set()
    seen = set()
    for row in rows:
        if row.status == "READY" and (row.dedup_key in existing or row.dedup_key in seen):
            row.status = "DUPLICATE"
        if row.dedup_key:
            seen.add(row.dedup_key)
    job.error_rows = sum(row.status == "ERROR" for row in rows)
    job.skipped_rows = sum(row.status == "DUPLICATE" for row in rows)
    db.commit()
    db.refresh(job)
    return job_out(db, job)


@router.post("/imports/{job_id}/confirm", response_model=ImportJobOut)
def confirm_import(job_id: int, user: CurrentUser, db: DbSession):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    job = owned_job(db, user.id, job_id)
    if job.status != "PREVIEWED":
        raise HTTPException(409, "Primero previsualiza la importación")
    rows = list(db.scalars(select(ImportRow).where(
        ImportRow.job_id == job.id, ImportRow.sheet_name == job.selected_sheet
    ).order_by(ImportRow.row_number)))
    ready_keys = [row.dedup_key for row in rows if row.status == "READY"]
    existing = set(db.scalars(select(ImportKey.key).where(
        ImportKey.user_id == user.id, ImportKey.key.in_(ready_keys)
    ))) if ready_keys else set()
    imported = 0
    skipped = 0
    for row in rows:
        if row.status != "READY":
            skipped += 1
            continue
        if row.dedup_key in existing:
            row.status = "DUPLICATE"
            skipped += 1
            continue
        values = TransactionIn.model_validate(row.parsed).model_dump()
        validate_transaction(db, user.id, values)
        movement = Transaction(user_id=user.id, **values)
        db.add(movement)
        db.flush()
        db.add(ImportKey(user_id=user.id, key=row.dedup_key, transaction_id=movement.id))
        row.transaction_id = movement.id
        row.status = "IMPORTED"
        existing.add(row.dedup_key)
        imported += 1
    db.flush()
    balances = account_balances(db, user.id)
    for account_id, cost in db.execute(select(
        InvestmentPosition.account_id, func.sum(InvestmentPosition.cost_basis)
    ).where(InvestmentPosition.user_id == user.id).group_by(InvestmentPosition.account_id)):
        if balances[account_id] < cost:
            raise HTTPException(409, "La importación dejaría una cuenta de inversión sin saldo para sus posiciones")
    job.imported_rows = imported
    job.skipped_rows = skipped
    job.status = "CONFIRMED"
    db.commit()
    db.refresh(job)
    return job_out(db, job)


def safe_spreadsheet(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.get("/exports/transactions")
def export_transactions(user: CurrentUser, db: DbSession, format: Literal["json", "csv", "xlsx"] = "csv"):
    accounts_by_id, categories_by_id, _, _ = reference_index(db, user.id)
    movements = list(db.scalars(select(Transaction).where(
        Transaction.user_id == user.id
    ).order_by(Transaction.date, Transaction.id)))
    rows = []
    for movement in movements:
        rows.append({
            "date": movement.date.isoformat(), "type": movement.type,
            "concept": movement.concept, "amount": str(movement.amount),
            "source_account": account_label(accounts_by_id[movement.source_account_id]) if movement.source_account_id else None,
            "destination_account": account_label(accounts_by_id[movement.destination_account_id]) if movement.destination_account_id else None,
            "category": category_label(categories_by_id[movement.category_id], categories_by_id) if movement.category_id else None,
            "status": movement.status, "notes": movement.notes,
            "payment_method": movement.payment_method,
            "is_fixed": movement.is_fixed, "is_necessary": movement.is_necessary,
        })
    if format == "json":
        content = json.dumps(rows, ensure_ascii=False, indent=2).encode()
        media_type = "application/json"
    elif format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows({key: safe_spreadsheet(value) for key, value in row.items()} for row in rows)
        content = buffer.getvalue().encode("utf-8-sig")
        media_type = "text/csv; charset=utf-8"
    else:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Movimientos")
        sheet.append(EXPORT_FIELDS)
        for row in rows:
            sheet.append([safe_spreadsheet(row[field]) for field in EXPORT_FIELDS])
        buffer = io.BytesIO()
        workbook.save(buffer)
        content = buffer.getvalue()
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="spiderfinance-movimientos.{format}"',
    })
