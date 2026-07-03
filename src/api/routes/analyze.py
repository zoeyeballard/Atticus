"""POST /analyze — analyze an office action into structured form + verification."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator

from src.config.data_classification import DataClass
from src.data import office_action_parser
from src.data.uspto_client import USPTOClient, USPTOError
from src.db.repositories import AuditEvent, get_repository
from src.generation.llm_client import DataClassificationError
from src.models.schemas import OfficeActionAnalysis, VerificationReport
from src.verification import hallucination_detector

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    application_number: str | None = None
    office_action_text: str | None = None
    allow_unpublished: bool = False  # compliance override; requires authorization

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
    publication_verified = text is not None  # pasted text: publication status is the user's call
    if text is None:
        try:
            with USPTOClient() as client:
                # Compliance guard: never index unpublished applications (35 U.S.C. 122(a)).
                if not req.allow_unpublished and not client.is_published(req.application_number or ""):
                    raise HTTPException(
                        403,
                        f"Application {req.application_number} does not appear to be published. "
                        "Unpublished applications are confidential under 35 U.S.C. 122(a); "
                        "Atticus only indexes published patent data.",
                    )
                publication_verified = True
                text = client.get_office_action_text(req.application_number or "")
        except USPTOError as exc:
            # No-OA / bad-app-number cases surface as 404; auth/connectivity as 502.
            msg = str(exc)
            status = 404 if "No office action" in msg else 502
            raise HTTPException(status, f"USPTO fetch failed: {exc}") from exc

    # Published applications are PUBLIC data; anything else is treated as CLIENT for the routing
    # guard (a training-enabled provider tier will refuse CLIENT data).
    data_class = DataClass.PUBLIC if publication_verified else DataClass.CLIENT
    try:
        analysis = office_action_parser.parse(
            text, application_number=req.application_number, data_class=data_class
        )
        verification = hallucination_detector.verify_output(
            analysis.raw_text or text, data_class=data_class
        )
    except DataClassificationError as exc:
        raise HTTPException(
            403,
            {
                "error": {
                    "code": "PROVIDER_NOT_PERMITTED_FOR_CLIENT_DATA",
                    "message": str(exc),
                    "suggestion": "Switch to a no-training provider in Settings "
                    "(Anthropic, or Gemini paid tier) before analyzing client data.",
                }
            },
        ) from exc

    repo = get_repository()
    analysis_id = repo.save_analysis(analysis, publication_verified=publication_verified)
    repo.append_audit(analysis_id, AuditEvent(step="generated", payload={"source": "analyze"}))
    repo.append_audit(
        analysis_id,
        AuditEvent(step="verified", payload={"confidence": verification.overall_confidence}),
    )

    return AnalyzeResponse(
        analysis_id=analysis_id, analysis=analysis, verification=verification
    )
