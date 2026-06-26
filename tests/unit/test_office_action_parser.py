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


def test_rejection_type_bare_final_word_is_not_final():
    # Real non-final OAs contain the word "final" in after-final boilerplate; that must NOT
    # flip the type to final (the bug found scoring live OAs 19418983/19445647).
    text = "DETAILED ACTION\nApplicant may reply to a final rejection by filing a response."
    assert office_action_parser._detect_rejection_type(text) == "non-final"


def test_rejection_type_made_final():
    text = "DETAILED ACTION\nTHIS ACTION IS MADE FINAL. Claims 1-3 rejected under 35 U.S.C. 103."
    assert office_action_parser._detect_rejection_type(text) == "final"


def test_rejection_type_advisory():
    text = "ADVISORY ACTION\nThe reply filed after final has been considered."
    assert office_action_parser._detect_rejection_type(text) == "advisory"


def test_rejection_type_override_from_doc_code():
    # The authoritative document code overrides text heuristics.
    text = "THIS ACTION IS MADE FINAL."
    a = office_action_parser.parse(text, use_llm=False, rejection_type="non-final")
    assert a.rejection_type == "non-final"


def test_parse_without_llm_is_offline_safe(sample_office_action):
    analysis = office_action_parser.parse(sample_office_action, use_llm=False)
    assert analysis.raw_text == sample_office_action
    # The offline path now structures the § 103 rejection of claims 1-3 deterministically.
    assert {r.claim_number for r in analysis.rejections} == {1, 2, 3}
    assert analysis.confidence_score == 0.6  # deterministic-structured (not LLM) confidence
