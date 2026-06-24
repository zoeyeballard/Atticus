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
                text = client.get_office_action_text(req.application_number or "")
        except USPTOError as exc:
            # No-OA / bad-app-number cases surface as 404; auth/connectivity as 502.
            msg = str(exc)
            status = 404 if "No office action" in msg else 502
            raise HTTPException(status, f"USPTO fetch failed: {exc}") from exc

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
