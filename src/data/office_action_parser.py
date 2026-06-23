"""Parse raw office-action text into a structured ``OfficeActionAnalysis``.

Office actions are semi-structured text. We use a two-stage approach:

1. **Deterministic pre-extraction** (regex) pulls out the high-signal, unambiguous fields:
   application number, mailing date, rejection type, statutory bases present, and cited patent
   numbers. These are cheap and reliable and give us a verifiable scaffold.
2. **LLM-assisted structuring** (optional) fills in the harder claim→limitation→reference
   mappings, *constrained* to the references the regex already found, and validated against the
   Pydantic schema. The model never invents patent numbers — it may only map to references that
   deterministic extraction confirmed are present in the text.

If the Anthropic key is not configured, ``parse`` returns the regex-only scaffold so the data
pipeline is still exercisable offline.
"""

from __future__ import annotations

import logging
import re

from src.models.schemas import (
    CitedReference,
    OfficeActionAnalysis,
    RejectionBasis,
)

logger = logging.getLogger(__name__)

# US patent / publication numbers, e.g. "US 10,234,567 B2", "US2020/0123456 A1", "6,123,456".
_PATENT_RE = re.compile(
    r"\bUS[\s-]?\d{4}/\d{6,7}\s?[A-Z]?\d?"  # publication
    r"|\bUS[\s-]?[\d,]{7,12}\s?[A-Z]?\d?"  # grant with US prefix
    r"|\b\d{1,2},\d{3},\d{3}\b",  # bare grant number
)

_APP_NO_RE = re.compile(r"Application\s+No\.?\s*[:#]?\s*([\d/,]{8,})", re.IGNORECASE)
_MAIL_DATE_RE = re.compile(
    r"(?:Mail(?:ing)?\s*Date|Notification\s*Date)\s*[:#]?\s*([A-Za-z0-9,/ -]{6,20})",
    re.IGNORECASE,
)
_ART_UNIT_RE = re.compile(r"Art\s*Unit\s*[:#]?\s*(\d{3,4})", re.IGNORECASE)
_EXAMINER_RE = re.compile(r"Examiner\s*[:#]?\s*([A-Z][A-Za-z.\- ]{3,40})")

_BASIS_PATTERNS: list[tuple[RejectionBasis, re.Pattern[str]]] = [
    (RejectionBasis.SEC_101, re.compile(r"35\s*U\.?S\.?C\.?\s*§*\s*101")),
    (RejectionBasis.SEC_102, re.compile(r"35\s*U\.?S\.?C\.?\s*§*\s*102")),
    (RejectionBasis.SEC_103, re.compile(r"35\s*U\.?S\.?C\.?\s*§*\s*103")),
    (RejectionBasis.SEC_112_A, re.compile(r"§*\s*112\s*\(?a\)?|first\s+paragraph")),
    (RejectionBasis.SEC_112_B, re.compile(r"§*\s*112\s*\(?b\)?|second\s+paragraph")),
    (RejectionBasis.DOUBLE_PATENTING, re.compile(r"double\s+patenting", re.IGNORECASE)),
]


def _detect_rejection_type(text: str) -> str:
    lowered = text.lower()
    if "advisory action" in lowered:
        return "advisory"
    if re.search(r"\bfinal\b", lowered) and "non-final" not in lowered:
        return "final"
    return "non-final"


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def extract_cited_references(text: str) -> list[CitedReference]:
    """Deterministically extract candidate cited references from OA text."""
    seen: set[str] = set()
    refs: list[CitedReference] = []
    for match in _PATENT_RE.finditer(text):
        raw = re.sub(r"\s+", "", match.group(0))
        if raw in seen:
            continue
        seen.add(raw)
        refs.append(CitedReference(patent_number=raw))
    return refs


def detect_bases(text: str) -> list[RejectionBasis]:
    return [basis for basis, pattern in _BASIS_PATTERNS if pattern.search(text)]


def parse_scaffold(text: str, application_number: str | None = None) -> OfficeActionAnalysis:
    """Regex-only structured scaffold. Deterministic and offline-safe."""
    app_no = application_number or _first(_APP_NO_RE, text) or "UNKNOWN"
    return OfficeActionAnalysis(
        application_number=app_no,
        examiner_name=_first(_EXAMINER_RE, text),
        art_unit=_first(_ART_UNIT_RE, text),
        mailing_date=_first(_MAIL_DATE_RE, text) or "",
        rejection_type=_detect_rejection_type(text),
        raw_text=text,
        # rejections/mappings filled by the LLM stage; bases recorded as flags for now.
        unverified_claims=[f"§{b.value} rejection detected" for b in detect_bases(text)],
        confidence_score=0.4,  # scaffold-only confidence
    )


def parse(text: str, application_number: str | None = None, use_llm: bool = True) -> OfficeActionAnalysis:
    """Parse OA text into an ``OfficeActionAnalysis``.

    With ``use_llm=True`` and a configured Anthropic key, the claim→limitation→reference
    mappings are filled in by the analyzer pipeline. Otherwise returns the regex scaffold.
    """
    scaffold = parse_scaffold(text, application_number)
    if not use_llm:
        return scaffold
    try:
        # Imported lazily to avoid a hard dependency on the LLM client for offline parsing.
        from src.generation.oa_analyzer import structure_office_action

        return structure_office_action(text, scaffold)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully to the scaffold
        logger.warning("LLM structuring unavailable (%s); returning regex scaffold.", exc)
        return scaffold
