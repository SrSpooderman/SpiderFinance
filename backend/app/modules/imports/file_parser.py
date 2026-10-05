"""Lectura acotada de CSV/XLSX y normalización de filas financieras."""

import csv
import io
import json
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook
from app.modules.imports.domain import (string_value, parse_date, parse_amount, parse_bool, unescape_spreadsheet, parse_row)
from openpyxl.utils.exceptions import InvalidFileException

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 50
PORTABLE_FIELDS = [
    "date", "type", "concept", "amount", "source_account", "destination_account",
    "category", "status", "notes", "payment_method", "is_fixed", "is_necessary",
]


def unique_headers(values: list[str]) -> list[str]:
    result = []
    counts: dict[str, int] = {}
    for index, value in enumerate(values, 1):
        base = value.strip() or f"Columna {index}"
        counts[base] = counts.get(base, 0) + 1
        result.append(base if counts[base] == 1 else f"{base} ({counts[base]})")
    return result


def sheet_rows(rows, name: str) -> tuple[list[str], list[tuple[int, dict]]]:
    iterator = iter(rows)
    try:
        headers = unique_headers([string_value(value) for value in next(iterator)])
    except StopIteration:
        raise ValueError(f"La hoja {name} está vacía") from None
    if not headers or len(headers) > MAX_COLUMNS:
        raise ValueError("Demasiadas columnas")
    data = []
    for row_number, values in enumerate(iterator, 2):
        if len(data) >= MAX_ROWS:
            raise ValueError(f"El archivo supera {MAX_ROWS} filas")
        cells = [string_value(value) for value in values]
        if any(cells):
            data.append((row_number, dict(zip(headers, cells, strict=False))))
    return headers, data


def parse_file(contents: bytes, filename: str) -> dict[str, tuple[list[str], list[tuple[int, dict]]]]:
    if len(contents) > MAX_FILE_BYTES:
        raise ValueError("El archivo supera 5 MB")
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        try:
            records = json.loads(contents.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("El JSON no es válido o no está codificado en UTF-8") from None
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            raise ValueError("El JSON debe ser una lista de movimientos")
        if len(records) > MAX_ROWS:
            raise ValueError(f"El archivo supera {MAX_ROWS} filas")
        headers = list(dict.fromkeys(key for record in records for key in record)) if records else PORTABLE_FIELDS
        if not headers or len(headers) > MAX_COLUMNS or any(not isinstance(key, str) for key in headers):
            raise ValueError("El JSON no contiene columnas válidas")
        return {"JSON": sheet_rows([headers, *([record.get(key) for key in headers] for record in records)], "JSON")}
    if suffix == ".csv":
        try:
            content = contents.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("El CSV debe estar codificado en UTF-8") from None
        sample = content[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return {"CSV": sheet_rows(csv.reader(io.StringIO(content), dialect), "CSV")}
    if suffix != ".xlsx":
        raise ValueError("Solo se admiten CSV, XLSX y JSON")
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("El XLSX descomprimido supera 20 MB")
        workbook = load_workbook(io.BytesIO(contents), read_only=True, data_only=True, keep_links=False)
    except (zipfile.BadZipFile, InvalidFileException, OSError, KeyError, TypeError) as exc:
        raise ValueError("El XLSX no es válido") from exc
    try:
        if not workbook.sheetnames:
            raise ValueError("El XLSX no contiene hojas")
        result = {}
        total = 0
        for sheet in workbook:
            headers, rows = sheet_rows(sheet.values, sheet.title)
            total += len(rows)
            if total > MAX_ROWS:
                raise ValueError(f"El archivo supera {MAX_ROWS} filas")
            result[sheet.title] = (headers, rows)
        return result
    finally:
        workbook.close()


