"""Phase 3 API contract tests — no LLM key required.

Covers Excel upload, multi-dataset binding into one session, df_name uniqueness,
and the GET /sessions switcher list.
"""
import io

import pandas as pd


def _xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def test_upload_xlsx_accepted(api_client):
    df = pd.DataFrame({"dept": ["Eng", "Sales"], "salary": [100, 90]})
    r = api_client.post(
        "/datasets",
        files={
            "file": (
                "people.xlsx",
                io.BytesIO(_xlsx_bytes(df)),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 2
    assert data["df_name"] == "people"
    assert {c["name"] for c in data["columns"]} == {"dept", "salary"}


def test_upload_unsupported_extension_rejected(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400
    assert "Excel" in r.json()["detail"]["message"]


def test_second_dataset_binds_into_same_session(api_client):
    csv1 = "emp_id,dept\n1,Eng\n2,Sales\n"
    up1 = api_client.post(
        "/datasets",
        files={"file": ("employees.csv", io.BytesIO(csv1.encode()), "text/csv")},
    ).json()["data"]
    sid = up1["session_id"]

    # second upload (xlsx) into the SAME session
    df = pd.DataFrame({"emp_id": [1, 2], "salary": [100, 90]})
    up2 = api_client.post(
        "/datasets",
        data={"session_id": sid},
        files={
            "file": (
                "salaries.xlsx",
                io.BytesIO(_xlsx_bytes(df)),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()["data"]
    assert up2["session_id"] == sid

    detail = api_client.get(f"/sessions/{sid}").json()["data"]
    assert len(detail["datasets"]) == 2
    names = {d["df_name"] for d in detail["datasets"]}
    assert names == {"employees", "salaries"}


def test_df_name_collision_is_suffixed(api_client):
    csv = "a,b\n1,2\n"
    up1 = api_client.post(
        "/datasets",
        files={"file": ("data.csv", io.BytesIO(csv.encode()), "text/csv")},
    ).json()["data"]
    sid = up1["session_id"]
    assert up1["df_name"] == "data"

    up2 = api_client.post(
        "/datasets",
        data={"session_id": sid},
        files={"file": ("data.csv", io.BytesIO(csv.encode()), "text/csv")},
    ).json()["data"]
    assert up2["df_name"] == "data_2"


def test_list_sessions_shape_and_order(api_client):
    # session A
    a = api_client.post(
        "/datasets",
        files={"file": ("a.csv", io.BytesIO(b"x,y\n1,2\n"), "text/csv")},
    ).json()["data"]
    # session B
    b = api_client.post(
        "/datasets",
        files={"file": ("b.csv", io.BytesIO(b"x,y\n3,4\n"), "text/csv")},
    ).json()["data"]

    r = api_client.get("/sessions")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    rows = body["data"]
    assert len(rows) == 2
    row = rows[0]
    for key in (
        "session_id",
        "title",
        "created_at",
        "updated_at",
        "dataset_count",
        "datasets",
        "message_count",
        "last_question",
    ):
        assert key in row, key

    ids = {x["session_id"] for x in rows}
    assert ids == {a["session_id"], b["session_id"]}
    # newest-first by updated_at
    times = [x["updated_at"] for x in rows]
    assert times == sorted(times, reverse=True)

    by_id = {x["session_id"]: x for x in rows}
    assert by_id[a["session_id"]]["dataset_count"] == 1
    assert by_id[a["session_id"]]["datasets"] == ["a"]
