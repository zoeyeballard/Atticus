"""POST /verify-claim — verify a single claim against a cited source."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.models.schemas import VerifiedClaim
from src.verification.citation_verifier import verify_citation
from src.verification.entailment_checker import check_entailment
from src.verification.hallucination_detector import VerificationStatus

router = APIRouter(tags=["verify"])


class VerifyRequest(BaseModel):
    claim_text: str
    cited_source: str | None = None  # source text to check the claim against
    claim_type: str = "citation"


@router.post("/verify-claim", response_model=VerifiedClaim)
def verify_claim(req: VerifyRequest) -> VerifiedClaim:
    result = verify_citation(req.claim_text, req.claim_type)
    # If a source text was supplied and the citation exists, run entailment for characterization.
    if req.cited_source and result.status == VerificationStatus.VERIFIED:
        ent = check_entailment(req.cited_source, req.claim_text)
        result.status = ent["status"]
        result.source_span = req.cited_source[:200]
        result.explanation = ent["explanation"] or result.explanation
    return result
