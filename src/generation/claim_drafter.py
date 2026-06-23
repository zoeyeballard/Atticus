"""Draft / amend patent claims that distinguish over cited art.

A thin wrapper over the SUGGEST_AMENDMENTS prompt for the standalone "amend this claim" use case
(as opposed to the full response-drafting pipeline). New matter is disallowed: every amendment
must quote its written-description support from the specification.
"""

from __future__ import annotations

from src.generation.llm_client import LLMClient
from src.generation.prompt_templates import SUGGEST_AMENDMENTS


def suggest_amendment(
    claim_number: int,
    claim_text: str,
    specification_support: str,
    reference_passages: list[str],
    llm: LLMClient | None = None,
) -> dict:
    """Return a suggested amendment with its specification support and distinction."""
    llm = llm or LLMClient()
    refs = "\n".join(
        f"<cited_reference>\n{p}\n</cited_reference>" for p in reference_passages
    ) or "<cited_reference>(none)</cited_reference>"
    prompt = SUGGEST_AMENDMENTS
    user = prompt.render(
        claim_number=claim_number,
        claim_text=claim_text,
        specification_support=specification_support,
        reference_blocks=refs,
    )
    return llm.complete_json(prompt.system, user)
