"""Reformulate natural-language queries / claim limitations for effective patent search.

Patent search is sensitive to terminology: acronyms, synonyms, and the stilted phrasing of
claim language all hurt recall. This module expands a raw query into a retrieval-friendly form.
The deterministic expansion (acronym + synonym tables) runs always; an optional LLM expansion
can be layered on when configured.
"""

from __future__ import annotations

import re

# Common embedded-systems / computer-architecture acronyms (TC 2100/2600).
_ACRONYMS: dict[str, str] = {
    "cpu": "central processing unit",
    "gpu": "graphics processing unit",
    "mmu": "memory management unit",
    "dma": "direct memory access",
    "isr": "interrupt service routine",
    "irq": "interrupt request",
    "soc": "system on chip",
    "fpga": "field programmable gate array",
    "asic": "application specific integrated circuit",
    "rtos": "real time operating system",
    "tlb": "translation lookaside buffer",
    "alu": "arithmetic logic unit",
    "i/o": "input output",
    "dsp": "digital signal processor",
}

_SYNONYMS: dict[str, list[str]] = {
    "processor": ["processing unit", "controller", "microprocessor"],
    "memory": ["storage", "ram", "cache"],
    "priority queue": ["priority-ordered buffer", "ordered queue"],
    "interrupt": ["exception", "trap"],
}

_CLAIM_BOILERPLATE = re.compile(
    r"\b(?:configured to|wherein|comprising|the|a|an|said|at least one)\b",
    re.IGNORECASE,
)


def expand_acronyms(query: str) -> str:
    """Append expansions for any recognized acronyms found in the query."""
    expansions = []
    for token in re.findall(r"[A-Za-z/]+", query):
        key = token.lower()
        if key in _ACRONYMS:
            expansions.append(_ACRONYMS[key])
    return query + (" " + " ".join(expansions) if expansions else "")


def add_synonyms(query: str) -> str:
    lowered = query.lower()
    extras = [syn for term, syns in _SYNONYMS.items() if term in lowered for syn in syns]
    return query + (" " + " ".join(extras) if extras else "")


def strip_claim_boilerplate(limitation: str) -> str:
    """Remove low-information claim boilerplate so the embedding focuses on substance."""
    return re.sub(r"\s+", " ", _CLAIM_BOILERPLATE.sub(" ", limitation)).strip()


def reformulate(query: str, *, is_claim_limitation: bool = False) -> str:
    """Produce a retrieval-optimized query string."""
    text = strip_claim_boilerplate(query) if is_claim_limitation else query
    text = expand_acronyms(text)
    text = add_synonyms(text)
    return text
