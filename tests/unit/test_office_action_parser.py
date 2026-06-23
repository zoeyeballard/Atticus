"""Tests for the deterministic office-action parsing stage."""

from src.data import office_action_parser
from src.models.schemas import RejectionBasis


def test_scaffold_extracts_metadata(sample_office_action):
    analysis = office_action_parser.parse_scaffold(sample_office_action)
    assert analysis.application_number == "16/123,456"
    assert analysis.art_unit == "2186"
    assert analysis.rejection_type == "non-final"
    assert "SMITH" in (analysis.examiner_name or "").upper()


def test_detects_103_basis(sample_office_action):
    bases = office_action_parser.detect_bases(sample_office_action)
    assert RejectionBasis.SEC_103 in bases


def test_extracts_cited_references(sample_office_action):
    refs = office_action_parser.extract_cited_references(sample_office_action)
    numbers = {r.patent_number for r in refs}
    assert any("9876543" in n.replace(",", "") for n in numbers)
    assert any("2019/0123456" in n for n in numbers)


def test_parse_without_llm_is_offline_safe(sample_office_action):
    analysis = office_action_parser.parse(sample_office_action, use_llm=False)
    assert analysis.raw_text == sample_office_action
    assert analysis.confidence_score < 0.5  # scaffold-only confidence
