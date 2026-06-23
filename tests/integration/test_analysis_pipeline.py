"""Integration test: API analyze endpoint with text input, offline (no LLM/USPTO)."""

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "")  # force offline scaffold path

from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analyze_with_text(sample_office_action):
    resp = client.post("/api/v1/analyze", json={"office_action_text": sample_office_action})
    assert resp.status_code == 200
    body = resp.json()
    assert body["analysis"]["application_number"] == "16/123,456"
    assert body["analysis"]["rejection_type"] == "non-final"
    assert "analysis_id" in body
    assert "verification" in body


def test_analyze_requires_input():
    resp = client.post("/api/v1/analyze", json={})
    assert resp.status_code == 422
