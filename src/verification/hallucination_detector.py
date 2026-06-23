"""Orchestrate the full verification pipeline.

decompose → citation_verifier → entailment_checker → confidence_scorer → VerificationReport.

This is the single entry point the API calls after any generation step. It logs every step to the
audit trail when enabled.
"""

from __future__ import annotations

import logging

from src.config import get_settings
from src.data.uspto_client import USPTOClient
from src.generation.llm_client import LLMClient
from src.models.schemas import (
    VerificationReport,
    VerificationStatus,
    VerifiedClaim,
)
from src.verification import claim_decomposer, confidence_scorer
from src.verification.citation_verifier import verify_citation
from src.verification.entailment_checker import check_entailment

logger = logging.getLogger(__name__)

_CITATION_TYPES = {"citation", "patent_reference"}


def verify_output(
    text: str,
    *,
    sources: dict[str, str] | None = None,
    known_mpep_sections: set[str] | None = None,
    uspto: USPTOClient | None = None,
    llm: LLMClient | None = None,
) -> VerificationReport:
    """Verify an AI-generated text end to end.

    Parameters
    ----------
    sources:
        Mapping of ``document_id`` → source text, used by the entailment checker to confirm that
        characterizations of a real source are actually supported.
    known_mpep_sections:
        The set of MPEP section numbers present in the indexed corpus (for existence checks).
    """
    sources = sources or {}
    llm = llm or LLMClient()
    owns_client = uspto is None
    uspto = uspto or USPTOClient()

    try:
        atomic = claim_decomposer.decompose(text, llm=llm)
        verified: list[VerifiedClaim] = []

        for item in atomic:
            claim_text = item.get("claim_text", "")
            claim_type = item.get("claim_type", "factual_assertion")

            if claim_type in _CITATION_TYPES:
                result = verify_citation(
                    claim_text, claim_type, uspto=uspto, known_mpep_sections=known_mpep_sections
                )
                # If the source exists, escalate to entailment to catch mischaracterization.
                if result.status == VerificationStatus.VERIFIED and result.source_document:
                    source_text = sources.get(result.source_document)
                    if source_text:
                        ent = check_entailment(source_text, claim_text, llm=llm)
                        result.status = ent["status"]
                        result.source_span = source_text[:200]
                        result.explanation = ent["explanation"] or result.explanation
                verified.append(result)
            else:
                verified.append(_verify_non_citation(claim_text, claim_type, sources, llm))

        report = confidence_scorer.score(verified)
        if get_settings().audit_trail_enabled:
            logger.info(
                "Verification complete: %d claims, confidence=%.2f, review=%s",
                report.total_claims,
                report.overall_confidence,
                report.needs_human_review,
            )
        return report
    finally:
        if owns_client:
            uspto.close()


def _verify_non_citation(
    claim_text: str, claim_type: str, sources: dict[str, str], llm: LLMClient
) -> VerifiedClaim:
    if claim_type == "opinion":
        return VerifiedClaim(
            claim_text=claim_text,
            claim_type=claim_type,
            status=VerificationStatus.UNVERIFIABLE,
            confidence=0.5,
            explanation="Opinion / subjective judgment — not independently verifiable.",
        )
    # Check the assertion against any provided source via entailment.
    if sources:
        combined = "\n\n".join(sources.values())[:8000]
        ent = check_entailment(combined, claim_text, llm=llm)
        return VerifiedClaim(
            claim_text=claim_text,
            claim_type=claim_type,
            status=ent["status"],
            confidence=0.7 if ent["status"] == VerificationStatus.VERIFIED else 0.4,
            explanation=ent["explanation"],
        )
    return VerifiedClaim(
        claim_text=claim_text,
        claim_type=claim_type,
        status=VerificationStatus.UNVERIFIABLE,
        confidence=0.3,
        explanation="No source provided to verify this assertion against.",
    )


def empty_report() -> VerificationReport:
    return VerificationReport()
