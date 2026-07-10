"""LLM-output validation in the analyzer: nulls and junk must degrade per-field, not per-analysis."""

from src.generation.oa_analyzer import _build_rejections


def test_null_fields_coerced_not_dropped():
    raw = [
        {
            "claim_number": 1,
            "rejection_basis": "103",
            "is_independent": True,
            "limitation_mappings": [
                {
                    "limitation_text": "a processor configured to receive interrupts",
                    "mapped_to_reference": "US10,234,567",
                    "reference_passage": None,  # LLMs emit explicit nulls
                    "examiner_reasoning": None,
                },
                {
                    "limitation_text": None,
                    "mapped_to_reference": None,
                    "reference_passage": None,
                },
            ],
            "cited_references": [
                {"patent_number": "US10,234,567", "relevant_passages": None},
            ],
        }
    ]
    rejections = _build_rejections(raw, known_numbers={"US10,234,567"})
    assert len(rejections) == 1
    r = rejections[0]
    assert len(r.limitation_mappings) == 2
    assert r.limitation_mappings[0].reference_passage == ""
    assert r.cited_references[0].relevant_passages == []


def test_reference_formats_normalized_for_matching():
    # The examiner writes "US 2015/0039705 A1"; deterministic extraction stored "US20150039705".
    # Formatting noise and kind codes must not cause real mappings to be dropped.
    raw = [
        {
            "claim_number": 21,
            "rejection_basis": "102",
            "limitation_mappings": [
                {
                    "limitation_text": "a display device",
                    "mapped_to_reference": "US 2015/0039705 A1",
                    "reference_passage": "para. [0042]",
                }
            ],
            "cited_references": [
                {"patent_number": "US 2015/0039705 A1", "relevant_passages": ["[0042]"]},
            ],
        }
    ]
    rejections = _build_rejections(raw, known_numbers={"US20150039705"})
    assert len(rejections[0].limitation_mappings) == 1
    assert len(rejections[0].cited_references) == 1


def test_unknown_reference_mappings_filtered():
    raw = [
        {
            "claim_number": None,  # null claim number must not crash int()
            "rejection_basis": "102",
            "limitation_mappings": [
                {
                    "limitation_text": "a queue",
                    "mapped_to_reference": "US99,999,999",  # not in the OA
                    "reference_passage": "col. 1",
                }
            ],
            "cited_references": [],
        }
    ]
    rejections = _build_rejections(raw, known_numbers={"US10,234,567"})
    assert rejections[0].claim_number == 0
    assert rejections[0].limitation_mappings == []
