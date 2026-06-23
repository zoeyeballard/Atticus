"""POST /analyze — analyze an office action into structured form + verification."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator

from src.data import office_action_parser
from src.data.uspto_client import USPTOClient, USPTOError
from src.db.repositories import AuditEvent, get_repository
from src.models.schemas import OfficeActionAnalysis, VerificationReport
from src.verification import hallucination_detector

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    application_number: str | None = None
    office_action_text: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "AnalyzeRequest":
        if not self.application_number and not self.office_action_text:
            raise ValueError("Provide either application_number or office_action_text.")
        return self


class AnalyzeResponse(BaseModel):
    analysis_id: str
    analysis: OfficeActionAnalysis
    verification: VerificationReport


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    text = req.office_action_text
    if text is None:
        try:
            with USPTOClient() as client:
                actions = client.get_office_actions(req.application_number or "")
                if not actions:
                    raise HTTPException(404, "No office action found for that application.")
                doc_id = actions[0].get("documentId") or actions[0].get("id")
                text = client.get_document_text(str(doc_id))
        except USPTOError as exc:
            raise HTTPException(502, f"USPTO fetch failed: {exc}") from exc

    analysis = office_action_parser.parse(text, application_number=req.application_number)

    repo = get_repository()
    analysis_id = repo.save_analysis(analysis)
    repo.append_audit(analysis_id, AuditEvent(step="generated", payload={"source": "analyze"}))

    # Verify the structured analysis text (sources passed in would tighten this further).
    verification = hallucination_detector.verify_output(analysis.raw_text or text)
    repo.append_audit(
        analysis_id,
        AuditEvent(step="verified", payload={"confidence": verification.overall_confidence}),
    )

    return AnalyzeResponse(
        analysis_id=analysis_id, analysis=analysis, verification=verification
    )
