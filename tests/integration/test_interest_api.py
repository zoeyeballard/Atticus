"""Integration tests for the interest-form endpoint (offline)."""

import json
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.routes import interest as interest_route  # noqa: E402
from src.main import app  # noqa: E402

client = TestClient(app)


def test_signup_recorded(tmp_path, monkeypatch):
    ledger = tmp_path / "interest.jsonl"
    monkeypatch.setattr(interest_route, "_LEDGER", ledger)

    resp = client.post(
        "/api/v1/interest",
        json={
            "name": "Jane Practitioner",
            "email": "jane@examplefirm.com",
            "organization": "Example Firm LLP",
            "role": "Patent attorney",
            "note": "Docketing-heavy 2100 practice.",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"recorded": True}

    lines = ledger.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["email"] == "jane@examplefirm.com"
    assert entry["received_at"]


def test_bad_email_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(interest_route, "_LEDGER", tmp_path / "interest.jsonl")
    resp = client.post("/api/v1/interest", json={"name": "X", "email": "not-an-email"})
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["error"]["code"] == "INVALID_EMAIL"


def test_missing_name_rejected():
    resp = client.post("/api/v1/interest", json={"name": "", "email": "a@b.co"})
    assert resp.status_code == 422  # pydantic min_length
