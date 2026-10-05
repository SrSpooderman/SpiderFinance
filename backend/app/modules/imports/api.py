import csv
import io
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from openpyxl import Workbook
from pydantic import BaseModel

from app.http.dependencies import CurrentUser, DbSession
from app.infrastructure.ledger_policies import SqlLedgerPolicies
from app.modules.ledger.schemas import TransactionIn
from app.modules.imports.application import Imports, safe_spreadsheet
from app.modules.imports.file_parser import MAX_FILE_BYTES, PORTABLE_FIELDS, parse_file
from app.modules.imports.infrastructure import SqlImportStore
from app.modules.ledger.application import Ledger
from app.modules.ledger.infrastructure import SqlLedgerStore

router = APIRouter(tags=["imports"])
EXPORT_FIELDS = PORTABLE_FIELDS


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


def imports(db: DbSession, user_id: int) -> Imports:
    ledger_store = SqlLedgerStore(db)
    ledger = Ledger(ledger_store, SqlLedgerPolicies(db))

    def validate(raw: dict) -> tuple[dict, dict]:
        parsed = TransactionIn.model_validate(raw)
        values = parsed.model_dump()
        ledger.validate_transaction(user_id, values)
        return values, parsed.model_dump(mode="json")

    return Imports(SqlImportStore(db, ledger_store), validate)


@router.get("/imports", response_model=list[ImportJobOut])
def list_jobs(user: CurrentUser, db: DbSession):
    return imports(db, user.id).list_jobs(user.id)


@router.get("/imports/{job_id}", response_model=ImportJobOut)
def read_job(job_id: int, user: CurrentUser, db: DbSession):
    return imports(db, user.id).read_job(user.id, job_id)


@router.delete("/imports/{job_id}", status_code=204)
def delete_job(job_id: int, user: CurrentUser, db: DbSession):
    imports(db, user.id).delete_job(user.id, job_id)


@router.get("/imports/{job_id}/sheets", response_model=dict[str, list[str]])
def read_sheet_headers(job_id: int, user: CurrentUser, db: DbSession):
    return imports(db, user.id).sheet_headers(user.id, job_id)


@router.post("/imports", response_model=ImportJobOut, status_code=201)
async def upload_import(user: CurrentUser, db: DbSession, file: UploadFile = File(...)):
    filename = Path(file.filename or "archivo").name[:255]
    contents = await file.read(MAX_FILE_BYTES + 1)
    try:
        sheets = parse_file(contents, filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return imports(db, user.id).create_job(user.id, filename, sheets)


@router.post("/imports/{job_id}/preview", response_model=ImportJobOut)
def preview_import(job_id: int, data: PreviewIn, user: CurrentUser, db: DbSession):
    return imports(db, user.id).preview(user.id, job_id, data.model_dump())


@router.post("/imports/{job_id}/confirm", response_model=ImportJobOut)
def confirm_import(job_id: int, user: CurrentUser, db: DbSession):
    return imports(db, user.id).confirm(user.id, job_id)


@router.get("/exports/transactions")
def export_transactions(user: CurrentUser, db: DbSession, format: Literal["json", "csv", "xlsx"] = "csv"):
    rows = imports(db, user.id).export_rows(user.id)
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
