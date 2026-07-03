"""Entailment / NLI checking — catches the sneakiest hallucination: real source, wrong claim.

Given (source_text, claim_about_source), determine whether the source SUPPORTS, CONTRADICTS, or is
NEUTRAL toward the claim. Uses Claude Haiku with a focused NLI prompt.
"""

from __future__ import annotations

import logging

from src.generation.llm_client import LLMClient
from src.generation.prompt_templates import ENTAILMENT_CHECK
from src.models.schemas import VerificationStatus

logger = logging.getLogger(__name__)

_VERDICT_TO_STATUS = {
    "ENTAILS": VerificationStatus.VERIFIED,
    "NEUTRAL": VerificationStatus.UNSUPPORTED,
    "CONTRADICTS": VerificationStatus.UNSUPPORTED,
}


def check_entailment(
    source_text: str, claim_text: str, llm: LLMClient | None = None, data_class=None
) -> dict:
    """Return ``{"verdict", "explanation", "status"}`` for a (source, claim) pair."""
    from src.config.data_classification import DataClass
    from src.generation.llm_client import DataClassificationError

    llm = llm or LLMClient()
    dc = data_class if data_class is not None else DataClass.CLIENT
    prompt = ENTAILMENT_CHECK
    user = prompt.render(source_text=source_text, claim_text=claim_text)
    try:
        data = llm.complete_json(prompt.system, user, max_tokens=512, data_class=dc)
        verdict = str(data.get("verdict", "NEUTRAL")).upper()
    except DataClassificationError:
        raise  # compliance blocks must surface
    except Exception as exc:  # noqa: BLE001
        logger.warning("Entailment check failed (%s); marking unverifiable.", exc)
        return {
            "verdict": "NEUTRAL",
            "explanation": f"Entailment check unavailable: {exc}",
            "status": VerificationStatus.UNVERIFIABLE,
        }
    status = _VERDICT_TO_STATUS.get(verdict, VerificationStatus.UNSUPPORTED)
    return {
        "verdict": verdict,
        "explanation": data.get("explanation", ""),
        "status": status,
    }
