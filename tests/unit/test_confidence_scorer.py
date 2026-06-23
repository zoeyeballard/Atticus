"""Tests for verification scoring rules."""

from src.models.schemas import VerificationStatus, VerifiedClaim
from src.verification import confidence_scorer


def _claim(status: VerificationStatus, claim_type: str = "citation") -> VerifiedClaim:
    return VerifiedClaim(
        claim_text="x", claim_type=claim_type, status=status, confidence=1.0, explanation=""
    )


def test_fabricated_citation_forces_review():
    report = confidence_scorer.score([_claim(VerificationStatus.FABRICATED)])
    assert report.needs_human_review is True
    assert report.fabricated_count == 1
    assert report.review_flags


def test_all_verified_high_confidence():
    report = confidence_scorer.score([_claim(VerificationStatus.VERIFIED) for _ in range(3)])
    assert report.needs_human_review is False
    assert report.overall_confidence == 1.0


def test_unsupported_lowers_confidence_and_flags():
    report = confidence_scorer.score(
        [_claim(VerificationStatus.VERIFIED), _claim(VerificationStatus.UNSUPPORTED)]
    )
    assert report.needs_human_review is True
    assert 0.0 < report.overall_confidence < 1.0
