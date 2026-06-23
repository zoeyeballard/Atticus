"""GET /audit-trail/{analysis_id} — full transparency for an analysis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.db.repositories import get_repository

router = APIRouter(tags=["audit"])


@router.get("/audit-trail/{analysis_id}")
def audit_trail(analysis_id: str) -> dict:
    repo = get_repository()
    if repo.get_analysis(analysis_id) is None:
        raise HTTPException(404, "Unknown analysis_id.")
    return {"analysis_id": analysis_id, "events": repo.get_audit_trail(analysis_id)}
