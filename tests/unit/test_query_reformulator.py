"""Tests for query reformulation."""

from src.retrieval import query_reformulator


def test_acronym_expansion():
    out = query_reformulator.expand_acronyms("a DMA controller for the CPU")
    assert "direct memory access" in out
    assert "central processing unit" in out


def test_strip_claim_boilerplate():
    out = query_reformulator.strip_claim_boilerplate(
        "a processor configured to handle interrupt requests"
    )
    assert "configured to" not in out
    assert "processor" in out


def test_reformulate_claim_limitation_adds_synonyms():
    out = query_reformulator.reformulate(
        "a processor configured to manage a priority queue", is_claim_limitation=True
    )
    assert "processor" in out
    assert "priority queue" in out or "ordered queue" in out
