from datetime import date
from io import BytesIO

from openpyxl import Workbook, load_workbook


def test_csv_preview_confirm_dedup_and_exports(client, auth):
    account = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "currency": "EUR",
    }).json()["id"]
    today = date.today().isoformat()
    content = (
        f"Fecha;Concepto;Importe\n{today};Nómina;100,00\n"
        f"{today};Alquiler;-25,00\n{today};Fila inválida;abc\n"
    ).encode()
    uploaded = client.post("/api/v1/imports", headers=auth, files={
        "file": ("extracto.csv", content, "text/csv"),
    })
    assert uploaded.status_code == 201, uploaded.text
    job_id = uploaded.json()["id"]
    payload = {
        "sheet_name": "CSV",
        "mapping": {"date": "Fecha", "concept": "Concepto", "amount": "Importe"},
        "default_account_id": account,
        "positive_is_income": True,
    }
    preview = client.post(f"/api/v1/imports/{job_id}/preview", headers=auth, json=payload)
    assert preview.status_code == 200, preview.text
    assert [row["status"] for row in preview.json()["rows"]] == ["READY", "READY", "ERROR"]
    confirmed = client.post(f"/api/v1/imports/{job_id}/confirm", headers=auth)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["imported_rows"] == 2
    assert confirmed.json()["skipped_rows"] == 1
    assert client.get(f"/api/v1/accounts/{account}/balance", headers=auth).json()["balance"] == "75.00"
    movement_id = client.get("/api/v1/transactions", headers=auth).json()["items"][0]["id"]
    assert client.delete(f"/api/v1/transactions/{movement_id}", headers=auth).status_code == 409
    duplicate = client.post("/api/v1/imports", headers=auth, files={
        "file": ("extracto.csv", content, "text/csv"),
    }).json()["id"]
    second = client.post(f"/api/v1/imports/{duplicate}/preview", headers=auth, json=payload)
    assert [row["status"] for row in second.json()["rows"]] == ["DUPLICATE", "DUPLICATE", "ERROR"]
    assert client.delete(f"/api/v1/imports/{job_id}", headers=auth).status_code == 204
    assert client.get("/api/v1/transactions", headers=auth).json()["total"] == 2

    exported_json = client.get("/api/v1/exports/transactions?format=json", headers=auth)
    assert exported_json.status_code == 200
    assert len(exported_json.json()) == 2
    exported_csv = client.get("/api/v1/exports/transactions?format=csv", headers=auth)
    assert exported_csv.status_code == 200
    assert "Nómina" in exported_csv.text
    exported_xlsx = client.get("/api/v1/exports/transactions?format=xlsx", headers=auth)
    assert exported_xlsx.status_code == 200
    workbook = load_workbook(BytesIO(exported_xlsx.content), read_only=True)
    assert len(list(workbook.active.values)) == 3
    workbook.close()


def test_xlsx_sheet_selection_and_isolation(client, auth):
    account = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "currency": "EUR",
    }).json()["id"]
    workbook = Workbook()
    first = workbook.active
    first.title = "Resumen"
    first.append(["Dato"])
    first.append(["Ignorar"])
    second = workbook.create_sheet("Movimientos")
    second.append(["Fecha", "Concepto", "Importe"])
    second.append([date.today(), "Compra", -12.5])
    buffer = BytesIO()
    workbook.save(buffer)
    upload = client.post("/api/v1/imports", headers=auth, files={
        "file": ("banco.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    })
    assert upload.status_code == 201, upload.text
    job_id = upload.json()["id"]
    assert upload.json()["sheet_names"] == ["Resumen", "Movimientos"]
    preview = client.post(f"/api/v1/imports/{job_id}/preview", headers=auth, json={
        "sheet_name": "Movimientos",
        "mapping": {"date": "Fecha", "concept": "Concepto", "amount": "Importe"},
        "default_account_id": account,
    })
    assert preview.status_code == 200, preview.text
    assert preview.json()["rows"][0]["status"] == "READY"
    other = client.post("/api/v1/auth/register", json={
        "email": "imports-other@example.com", "password": "another-strong-password",
    })
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get(f"/api/v1/imports/{job_id}", headers=other_auth).status_code == 404
