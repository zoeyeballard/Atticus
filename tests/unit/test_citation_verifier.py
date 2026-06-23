"""Tests for citation extraction / verification (no live USPTO calls)."""

from src.models.schemas import VerificationStatus
from src.verification import citation_verifier


class _FakeUSPTO:
    """Stub: only 9,876,543 exists."""

    def patent_exists(self, number: str) -> bool:
        return number.replace(",", "").replace(" ", "") == "US9876543"

    def close(self) -> None:  # noqa: D401
        pass


def test_extract_patent_numbers():
    text = "rejected over US 9,876,543 B2 and US2019/0123456 A1"
    numbers = citation_verifier.extract_patent_numbers(text)
    assert any("9876543" in n for n in numbers)


def test_fabricated_patent_flagged():
    result = citation_verifier.verify_citation(
        "See US 1,111,111 B2.", "citation", uspto=_FakeUSPTO()
    )
    assert result.status == VerificationStatus.FABRICATED


def test_real_patent_marked_verified_pending_entailment():
    result = citation_verifier.verify_citation(
        "See US 9,876,543 B2.", "citation", uspto=_FakeUSPTO()
    )
    assert result.status == VerificationStatus.VERIFIED


def test_mpep_section_existence_check():
    result = citation_verifier.verify_citation(
        "Per MPEP § 2143.01 the references...",
        "citation",
        uspto=_FakeUSPTO(),
        known_mpep_sections={"2143"},
    )
    assert result.status == VerificationStatus.FABRICATED
