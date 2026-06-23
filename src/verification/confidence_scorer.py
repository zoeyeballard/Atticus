"""Aggregate per-claim verification results into a ``VerificationReport``.

Rules (per CLAUDE.md):
  * If ANY citation is fabricated, flag the entire response for human review.
  * Weight by claim importance: a wrong patent number is worse than a slightly imprecise
    characterization.
"""

from __future__ import annotations

from src.models.schemas import (
    VerificationReport,
    VerificationStatus,
    VerifiedClaim,
)

# Importance weights by claim type — citations/patent references carry the most risk.
_TYPE_WEIGHT: dict[str, float] = {
    "citation": 1.0,
    "patent_reference": 1.0,
    "legal_proposition": 0.8,
    "factual_assertion": 0.6,
    "procedural_claim": 0.5,
    "opinion": 0.2,
}

_STATUS_SCORE: dict[VerificationStatus, float] = {
    VerificationStatus.VERIFIED: 1.0,
    VerificationStatus.PARTIALLY_SUPPORTED: 0.6,
    VerificationStatus.UNVERIFIABLE: 0.5,
    VerificationStatus.UNSUPPORTED: 0.1,
    VerificationStatus.FABRICATED: 0.0,
}


def score(claims: list[VerifiedClaim]) -> VerificationReport:
    counts = {status: 0 for status in VerificationStatus}
    weighted_sum = 0.0
    weight_total = 0.0
    flags: list[str] = []

    for claim in claims:
        counts[claim.status] += 1
        weight = _TYPE_WEIGHT.get(claim.claim_type, 0.6)
        weighted_sum += _STATUS_SCORE[claim.status] * weight
        weight_total += weight

        if claim.status == VerificationStatus.FABRICATED:
            flags.append(f"FABRICATED: {claim.claim_text[:120]} — {claim.explanation}")
        elif claim.status == VerificationStatus.UNSUPPORTED:
            flags.append(f"UNSUPPORTED: {claim.claim_text[:120]} — {claim.explanation}")

    overall = (weighted_sum / weight_total) if weight_total else 0.0
    needs_review = (
        counts[VerificationStatus.FABRICATED] > 0
        or counts[VerificationStatus.UNSUPPORTED] > 0
    )

    return VerificationReport(
        total_claims=len(claims),
        verified_count=counts[VerificationStatus.VERIFIED],
        partial_count=counts[VerificationStatus.PARTIALLY_SUPPORTED],
        unsupported_count=counts[VerificationStatus.UNSUPPORTED],
        fabricated_count=counts[VerificationStatus.FABRICATED],
        unverifiable_count=counts[VerificationStatus.UNVERIFIABLE],
        overall_confidence=round(overall, 3),
        claims=claims,
        needs_human_review=needs_review,
        review_flags=flags,
    )
