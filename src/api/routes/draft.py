"""POST /draft-response — draft a response from a stored analysis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db.repositories import AuditEvent, get_repository
from src.generation.response_drafter import draft_response
from src.models.schemas import ResponseDraft

router = APIRouter(tags=["draft"])


class DraftRequest(BaseModel):
    analysis_id: str
    strategy: str = "argue"  # "argue" | "amend" | "both"


@router.post("/draft-response", response_model=ResponseDraft)
def draft(req: DraftRequest) -> ResponseDraft:
    if req.strategy not in {"argue", "amend", "both"}:
        raise HTTPException(422, "strategy must be one of: argue, amend, both")

    repo = get_repository()
    analysis = repo.get_analysis(req.analysis_id)
    if analysis is None:
        raise HTTPException(404, "Unknown analysis_id.")

    draft_obj = draft_response(analysis, req.analysis_id, strategy=req.strategy)
    repo.save_draft(draft_obj)
    repo.append_audit(
        req.analysis_id,
        AuditEvent(step="generated", payload={"source": "draft", "strategy": req.strategy}),
    )
    return draft_obj
