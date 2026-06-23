"""Tests for the offline heuristic path of claim decomposition."""

from src.verification import claim_decomposer


class _BrokenLLM:
    """Forces the heuristic fallback by failing on any call."""

    def complete_json(self, *a, **k):  # noqa: D401
        raise RuntimeError("no api key")


def test_heuristic_decomposition_classifies_citations():
    text = "Anderson discloses a processor (col. 4, lines 23-45). The claim is obvious."
    claims = claim_decomposer.decompose(text, llm=_BrokenLLM())
    assert len(claims) >= 2
    types = {c["claim_type"] for c in claims}
    assert "citation" in types
