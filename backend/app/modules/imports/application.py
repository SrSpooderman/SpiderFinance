"""Import workflow and portable export records, independent of SQL and HTTP."""

import hashlib
import json
from pathlib import Path
from typing import Callable

from app.modules.errors import UseCaseError
from app.modules.imports.domain import parse_row, unescape_spreadsheet
from app.modules.imports.ports import ImportStore

FIELDS = {
    "date", "concept", "amount", "type", "account_id", "source_account_id",
    "destination_account_id", "category_id", "source_account", "destination_account",
    "category", "status", "notes", "payment_method", "is_fixed", "is_necessary", "external_id",
}


def account_label(account: dict) -> str:
    return f"{account['name']} [{account['currency']}]"


def category_label(category: dict, by_id: dict[int, dict]) -> str:
    return f"{by_id[category['parent_id']]['name']} / {category['name']}" if category["parent_id"] else category["name"]


def resolve_reference(value: str, references: dict[str, set[int]], kind: str) -> int:
    candidates = references.get(value, set())
    if not candidates:
        raise ValueError(f"{kind} no encontrada: {value}. Créala antes de importar o corrige el archivo")
    if len(candidates) != 1:
        raise ValueError(f"{kind} ambigua: {value}. Usa un nombre único en la instancia de destino")
    return next(iter(candidates))


def safe_spreadsheet(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


class Imports:
    def __init__(self, store: ImportStore, validate: Callable[[dict], tuple[dict, dict]]):
        self.store = store
        self.validate = validate

    def job(self, user_id: int, job_id: int) -> dict:
        item = self.store.job(user_id, job_id)
        if item is None:
            raise UseCaseError(404, "Importación no encontrada")
        return item

    def job_out(self, job: dict, include_rows: bool = True) -> dict:
        rows = self.store.rows(job["id"], job["selected_sheet"], limit=100) if include_rows else []
        return {**job, "rows": [{"row_number": row["row_number"], "raw": row["raw"],
                                  "parsed": row["parsed"], "error": row["error"], "status": row["status"]}
                                 for row in rows]}

    def list_jobs(self, user_id: int) -> list[dict]:
        return [self.job_out(job, include_rows=False) for job in self.store.jobs(user_id)]

    def read_job(self, user_id: int, job_id: int) -> dict:
        return self.job_out(self.job(user_id, job_id))

    def delete_job(self, user_id: int, job_id: int) -> None:
        self.job(user_id, job_id)
        self.store.delete_job(user_id, job_id)

    def sheet_headers(self, user_id: int, job_id: int) -> dict[str, list[str]]:
        job = self.job(user_id, job_id)
        result = {}
        for name in job["sheet_names"]:
            rows = self.store.rows(job_id, name, limit=1)
            result[name] = list(rows[0]["raw"]) if rows else (job["headers"] if name == job["selected_sheet"] else [])
        return result

    def create_job(self, user_id: int, filename: str, sheets: dict) -> dict:
        selected = next(iter(sheets))
        values = {
            "filename": filename, "file_type": Path(filename).suffix.lower().lstrip("."),
            "sheet_names": list(sheets), "selected_sheet": selected, "headers": sheets[selected][0],
            "mapping": {}, "default_account_id": None, "positive_is_income": True,
            "status": "UPLOADED", "total_rows": len(sheets[selected][1]), "imported_rows": 0,
            "skipped_rows": 0, "error_rows": 0,
        }
        return self.job_out(self.store.create_job(user_id, values, sheets))

    def reference_index(self, user_id: int):
        accounts = self.store.accounts(user_id)
        categories = self.store.categories(user_id)
        accounts_by_id = {item["id"]: item for item in accounts}
        categories_by_id = {item["id"]: item for item in categories}
        account_refs: dict[str, set[int]] = {}
        category_refs: dict[str, set[int]] = {}
        for item in accounts:
            account_refs.setdefault(account_label(item), set()).add(item["id"])
        for item in accounts:
            account_refs.setdefault(item["name"], set()).add(item["id"])
        for item in categories:
            category_refs.setdefault(category_label(item, categories_by_id), set()).add(item["id"])
        for item in categories:
            if item["parent_id"] is not None:
                category_refs.setdefault(item["name"], set()).add(item["id"])
        return accounts_by_id, categories_by_id, account_refs, category_refs

    def preview(self, user_id: int, job_id: int, data: dict) -> dict:
        job = self.job(user_id, job_id)
        if job["status"] == "CONFIRMED":
            raise UseCaseError(409, "La importación ya se confirmó")
        if data["sheet_name"] not in job["sheet_names"]:
            raise UseCaseError(422, "Hoja no encontrada")
        rows = self.store.rows(job_id, data["sheet_name"])
        headers = list(rows[0]["raw"]) if rows else job["headers"] if data["sheet_name"] == job["selected_sheet"] else []
        mapping = data["mapping"]
        if any(key not in FIELDS or value not in headers for key, value in mapping.items()):
            raise UseCaseError(422, "El mapeo contiene campos o columnas desconocidos")
        if any(field not in mapping for field in ("date", "concept", "amount")):
            raise UseCaseError(422, "Asigna fecha, concepto e importe")
        if data["default_account_id"] is not None and data["default_account_id"] not in {
            item["id"] for item in self.store.accounts(user_id)
        }:
            raise UseCaseError(404, "Cuenta no encontrada")
        _, _, account_refs, category_refs = self.reference_index(user_id)
        spreadsheet_safe = job["file_type"] in ("csv", "xlsx")
        occurrences: dict[str, int] = {}
        keys = []
        for row in rows:
            row["parsed"] = None
            row["error"] = None
            row["dedup_key"] = None
            try:
                raw_data = parse_row(row["raw"], mapping, data["default_account_id"],
                                     data["positive_is_income"], spreadsheet_safe)
                for field, target in (("source_account", "source_account_id"),
                                      ("destination_account", "destination_account_id")):
                    value = row["raw"].get(mapping.get(field, ""), "").strip()
                    if value:
                        if spreadsheet_safe:
                            value = unescape_spreadsheet(value)
                        raw_data[target] = resolve_reference(value, account_refs, "Cuenta")
                value = row["raw"].get(mapping.get("category", ""), "").strip()
                if value:
                    if spreadsheet_safe:
                        value = unescape_spreadsheet(value)
                    raw_data["category_id"] = resolve_reference(value, category_refs, "Categoría")
                _, normalized = self.validate(raw_data)
                external = row["raw"].get(mapping.get("external_id", ""), "")
                if external:
                    fingerprint = json.dumps({"account": normalized.get("source_account_id") or normalized.get("destination_account_id"),
                                              "external": str(external)}, sort_keys=True, ensure_ascii=False)
                else:
                    fingerprint = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
                    occurrences[fingerprint] = occurrences.get(fingerprint, 0) + 1
                    fingerprint += f":{occurrences[fingerprint]}"
                row["dedup_key"] = hashlib.sha256(fingerprint.encode()).hexdigest()
                row["parsed"] = normalized
                row["status"] = "READY"
                keys.append(row["dedup_key"])
            except (ValueError, UseCaseError) as exc:
                row["error"] = exc.message if isinstance(exc, UseCaseError) else str(exc)
                row["status"] = "ERROR"
        existing = self.store.existing_keys(user_id, keys)
        seen = set()
        for row in rows:
            if row["status"] == "READY" and (row["dedup_key"] in existing or row["dedup_key"] in seen):
                row["status"] = "DUPLICATE"
            if row["dedup_key"]:
                seen.add(row["dedup_key"])
        changes = {
            "selected_sheet": data["sheet_name"], "headers": headers, "mapping": mapping,
            "default_account_id": data["default_account_id"], "positive_is_income": data["positive_is_income"],
            "total_rows": len(rows), "imported_rows": 0, "status": "PREVIEWED",
            "error_rows": sum(row["status"] == "ERROR" for row in rows),
            "skipped_rows": sum(row["status"] == "DUPLICATE" for row in rows),
        }
        return self.job_out(self.store.update_job_and_rows(user_id, job_id, changes, rows))

    def confirm(self, user_id: int, job_id: int) -> dict:
        self.store.lock_user(user_id)
        job = self.job(user_id, job_id)
        if job["status"] != "PREVIEWED":
            raise UseCaseError(409, "Primero previsualiza la importación")
        rows = self.store.rows(job_id, job["selected_sheet"])
        keys = [row["dedup_key"] for row in rows if row["status"] == "READY"]
        existing = self.store.existing_keys(user_id, keys)
        imported = skipped = 0
        for row in rows:
            if row["status"] != "READY":
                skipped += 1
                continue
            if row["dedup_key"] in existing:
                row["status"] = "DUPLICATE"
                skipped += 1
                continue
            values, _ = self.validate(row["parsed"])
            row["transaction_id"] = self.store.add_imported_movement(user_id, values, row["dedup_key"])
            row["status"] = "IMPORTED"
            existing.add(row["dedup_key"])
            imported += 1
        balances = self.store.balances(user_id)
        for account_id, cost in self.store.investment_costs(user_id).items():
            if balances[account_id] < cost:
                raise UseCaseError(409, "La importación dejaría una cuenta de inversión sin saldo para sus posiciones")
        changes = {"imported_rows": imported, "skipped_rows": skipped, "status": "CONFIRMED"}
        return self.job_out(self.store.update_job_and_rows(user_id, job_id, changes, rows))

    def export_rows(self, user_id: int) -> list[dict]:
        accounts_by_id, categories_by_id, _, _ = self.reference_index(user_id)
        result = []
        for item in self.store.transactions(user_id):
            result.append({
                "date": item["date"].isoformat(), "type": item["type"], "concept": item["concept"],
                "amount": str(item["amount"]),
                "source_account": account_label(accounts_by_id[item["source_account_id"]]) if item["source_account_id"] else None,
                "destination_account": account_label(accounts_by_id[item["destination_account_id"]]) if item["destination_account_id"] else None,
                "category": category_label(categories_by_id[item["category_id"]], categories_by_id) if item["category_id"] else None,
                "status": item["status"], "notes": item["notes"], "payment_method": item["payment_method"],
                "is_fixed": item["is_fixed"], "is_necessary": item["is_necessary"],
            })
        return result
