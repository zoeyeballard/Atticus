"""Decompose AI output into atomic, classified, verifiable claims.

Uses Claude Haiku (fast, cheap, good at classification). Falls back to a sentence-level heuristic
split when the LLM is unavailable so the pipeline still produces something checkable offline.
"""

from __future__ import annotations

import logging
import re

from src.generation.llm_client import LLMClient
from src.generation.prompt_templates import DECOMPOSE_CLAIMS

logger = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[Source:|col\.\s*\d+|MPEP\s*§?\s*\d+|US[\s-]?[\d,]{7,}")
_SENTENCE_RE = re.compile(r"(?<=[.;])\s+(?=[A-Z])")


def _classify_heuristic(sentence: str) -> str:
    if _CITATION_RE.search(sentence):
        return "citation"
    if re.search(r"\bMPEP\b|\b§\s*\d+|\bobvious\b|\banticipat", sentence, re.IGNORECASE):
        return "legal_proposition"
    return "factual_assertion"


def decompose(text: str, llm: LLMClient | None = None, data_class=None) -> list[dict]:
    """Return a list of ``{"claim_text", "claim_type"}`` dicts."""
    from src.config.data_classification import DataClass
    from src.generation.llm_client import DataClassificationError

    llm = llm or LLMClient()
    dc = data_class if data_class is not None else DataClass.CLIENT
    try:
        prompt = DECOMPOSE_CLAIMS
        data = llm.complete_json(
            prompt.system, prompt.render(text=text), max_tokens=8192, data_class=dc
        )
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "claims" in data:
            return data["claims"]
    except DataClassificationError:
        raise  # compliance blocks must surface
    except Exception as exc:  # noqa: BLE001 — degrade to heuristic split
        logger.warning("LLM decomposition unavailable (%s); using heuristic split.", exc)

    sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
    return [{"claim_text": s, "claim_type": _classify_heuristic(s)} for s in sentences]
