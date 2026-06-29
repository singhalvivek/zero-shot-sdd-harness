"""API contract tests — no LLM key required (graph is not invoked)."""
import io


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_upload_csv_creates_dataset_and_session(api_client):
    csv = "dept,salary\nEng,100\nSales,90\n"
    r = api_client.post(
        "/datasets",
        files={"file": ("people.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 2
    assert data["df_name"] == "people"
    assert {c["name"] for c in data["columns"]} == {"dept", "salary"}
    assert data["session_id"]
    assert data["dataset_id"]


def test_upload_non_csv_rejected(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400


def test_upload_empty_csv_rejected(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 400


def test_get_session_not_found(api_client):
    r = api_client.get("/sessions/does-not-exist")
    assert r.status_code == 404


def test_get_session_returns_datasets(api_client):
    csv = "dept,salary\nEng,100\n"
    up = api_client.post(
        "/datasets",
        files={"file": ("p.csv", io.BytesIO(csv.encode()), "text/csv")},
    ).json()["data"]
    r = api_client.get(f"/sessions/{up['session_id']}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["session_id"] == up["session_id"]
    assert len(data["datasets"]) == 1
    assert data["messages"] == []


def test_ask_empty_question_rejected(api_client):
    csv = "dept,salary\nEng,100\n"
    up = api_client.post(
        "/datasets",
        files={"file": ("p.csv", io.BytesIO(csv.encode()), "text/csv")},
    ).json()["data"]
    r = api_client.post(f"/sessions/{up['session_id']}/ask", json={"question": "  "})
    assert r.status_code == 400


def test_ask_unknown_session_404(api_client):
    r = api_client.post("/sessions/nope/ask", json={"question": "hi"})
    assert r.status_code == 404


def test_ask_no_dataset_bound_400(api_client):
    # Create a bare session via the ORM (no dataset bound).
    from db.session import create_db_session
    from db.models import Session
    with create_db_session() as s:
        sess = Session()
        s.add(sess)
        s.flush()
        sid = sess.id
    r = api_client.post(f"/sessions/{sid}/ask", json={"question": "hi"})
    assert r.status_code == 400
