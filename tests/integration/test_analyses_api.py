"""Integration tests for the analyses CRUD/draft/export/delete API (offline)."""

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "")  # force deterministic/offline paths

from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402

client = TestClient(app)

_OA = (
    "Application No.: 16/123,456\nArt Unit: 2186\nDETAILED ACTION\n"
    "Claims 1-3 are rejected under 35 U.S.C. § 103 as being unpatentable over "
    "Anderson (US 9,876,543 B2) in view of Chen (US2019/0123456 A1).\n"
)


def _create() -> str:
    resp = client.post("/api/v1/analyze", json={"office_action_text": _OA})
    assert resp.status_code == 200, resp.text
    return resp.json()["analysis_id"]


def test_list_get_delete_lifecycle():
    aid = _create()

    listed = client.get("/api/v1/analyses").json()["analyses"]
    assert any(a["analysis_id"] == aid for a in listed)

    got = client.get(f"/api/v1/analyses/{aid}")
    assert got.status_code == 200
    assert got.json()["analysis"]["application_number"] == "16/123,456"

    # Hard delete purges it.
    assert client.delete(f"/api/v1/analyses/{aid}").status_code == 200
    assert client.get(f"/api/v1/analyses/{aid}").status_code == 404


def test_get_unknown_uses_error_envelope():
    resp = client.get("/api/v1/analyses/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["error"]["code"] == "ANALYSIS_NOT_FOUND"
    assert "suggestion" in body["error"]


def test_export_analysis_docx():
    aid = _create()
    resp = client.get(f"/api/v1/analyses/{aid}/export")
    assert resp.status_code == 200
    # DOCX is a zip; check the magic bytes.
    assert resp.content[:2] == b"PK"
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_source_lookup():
    aid = _create()
    resp = client.get(f"/api/v1/analyses/{aid}/sources/US9876543")
    assert resp.status_code == 200
    assert "9876543" in resp.json()["reference"]["patent_number"].replace(",", "")
