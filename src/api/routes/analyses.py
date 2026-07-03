"""Analysis CRUD + draft + source + export endpoints for the frontend.

All client-data access is tenant-scoped (default tenant for the prototype). Errors use the
consistent ``{"error": {code, message, suggestion}}`` shape the frontend renders directly.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from src.config.data_classification import DEFAULT_TENANT_ID
from src.db.repositories import AuditEvent, get_repository
from src.generation.docx_export import analysis_to_docx, draft_to_docx
from src.generation.response_drafter import draft_response
from src.models.schemas import OfficeActionAnalysis, ResponseDraft

router = APIRouter(tags=["analyses"])

_DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _err(code: str, message: str, suggestion: str = "") -> dict:
    return {"error": {"code": code, "message": message, "suggestion": suggestion}}


def _norm_ref(number: str) -> str:
    """Normalize a patent/publication number for comparison (drop separators, US prefix, kind code)."""
    s = re.sub(r"[\s,]", "", number or "").upper()
    s = re.sub(r"^US", "", s)
    return re.sub(r"[A-Z]\d?$", "", s)  # strip a trailing kind code like B2 / A1


def _require_analysis(analysis_id: str) -> OfficeActionAnalysis:
    analysis = get_repository().get_analysis(analysis_id, tenant_id=DEFAULT_TENANT_ID)
    if analysis is None:
        raise HTTPException(
            404,
            _err(
                "ANALYSIS_NOT_FOUND",
                f"No analysis found with id {analysis_id}.",
                "It may have been deleted or belong to a different account.",
            ),
        )
    return analysis


@router.get("/analyses")
def list_analyses(limit: int = 20) -> dict:
    return {"analyses": get_repository().list_analyses(tenant_id=DEFAULT_TENANT_ID, limit=limit)}


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict:
    return {"analysis_id": analysis_id, "analysis": _require_analysis(analysis_id).model_dump()}


class DraftRequest(BaseModel):
    strategy: str = "argue"


@router.post("/analyses/{analysis_id}/draft", response_model=ResponseDraft)
def create_draft(analysis_id: str, req: DraftRequest) -> ResponseDraft:
    if req.strategy not in {"argue", "amend", "both"}:
        raise HTTPException(422, _err("BAD_STRATEGY", "strategy must be argue, amend, or both."))
    analysis = _require_analysis(analysis_id)
    repo = get_repository()
    draft = draft_response(analysis, analysis_id, strategy=req.strategy)
    repo.save_draft(draft, tenant_id=DEFAULT_TENANT_ID)
    repo.append_audit(
        analysis_id,
        AuditEvent(step="generated", event_type="draft", payload={"strategy": req.strategy}),
        tenant_id=DEFAULT_TENANT_ID,
    )
    return draft


@router.get("/analyses/{analysis_id}/draft", response_model=ResponseDraft)
def get_draft(analysis_id: str) -> ResponseDraft:
    _require_analysis(analysis_id)
    draft = get_repository().get_draft(analysis_id, tenant_id=DEFAULT_TENANT_ID)
    if draft is None:
        raise HTTPException(404, _err("DRAFT_NOT_FOUND", "No draft yet for this analysis.",
                                      "Generate one with POST .../draft."))
    return draft


@router.put("/analyses/{analysis_id}/draft", response_model=ResponseDraft)
def save_draft(analysis_id: str, draft: ResponseDraft) -> ResponseDraft:
    _require_analysis(analysis_id)
    get_repository().save_draft(draft, tenant_id=DEFAULT_TENANT_ID)
    return draft


@router.get("/analyses/{analysis_id}/sources/{ref}")
def get_source(analysis_id: str, ref: str) -> dict:
    """Return the cited-reference metadata + passages the examiner relied on."""
    analysis = _require_analysis(analysis_id)
    for rej in analysis.rejections:
        for cited in rej.cited_references:
            if _norm_ref(cited.patent_number) == _norm_ref(ref):
                return {"reference": cited.model_dump()}
    raise HTTPException(404, _err("SOURCE_NOT_FOUND", f"Reference {ref} not found in this analysis."))


@router.get("/analyses/{analysis_id}/export")
def export_analysis(analysis_id: str) -> Response:
    analysis = _require_analysis(analysis_id)
    data = analysis_to_docx(analysis)
    return Response(
        content=data,
        media_type=_DOCX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="analysis_{analysis_id}.docx"'},
    )


@router.get("/analyses/{analysis_id}/draft/export")
def export_draft(analysis_id: str) -> Response:
    _require_analysis(analysis_id)
    draft = get_repository().get_draft(analysis_id, tenant_id=DEFAULT_TENANT_ID)
    if draft is None:
        raise HTTPException(404, _err("DRAFT_NOT_FOUND", "No draft to export."))
    data = draft_to_docx(draft)
    return Response(
        content=data,
        media_type=_DOCX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="response_{analysis_id}.docx"'},
    )


@router.delete("/analyses/{analysis_id}")
def delete_analysis(analysis_id: str) -> dict:
    """Hard delete (compliance — right to deletion): purges analysis, draft, and audit trail."""
    if not get_repository().delete_analysis(analysis_id, tenant_id=DEFAULT_TENANT_ID):
        raise HTTPException(404, _err("ANALYSIS_NOT_FOUND", f"No analysis with id {analysis_id}."))
    return {"deleted": analysis_id}
