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
    ClaimRejection,
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


# A final action carries the standard USPTO boilerplate "THIS ACTION IS MADE FINAL"; the bare
# word "final" appears in many non-final actions (boilerplate about after-final practice), so
# match the specific phrase, not \bfinal\b. The authoritative signal is the document code
# (CTNF/CTFR/CTAV) when available — see office_action_parser.parse(rejection_type=...).
_FINAL_MARKERS = (
    "this action is made final",
    "action is made final",
    "is hereby made final",
    "this action is final",
)


def _detect_rejection_type(text: str) -> str:
    lowered = text.lower()
    # An advisory action announces itself as a heading at the very top.
    if "advisory action" in lowered[:2000]:
        return "advisory"
    if any(marker in lowered for marker in _FINAL_MARKERS):
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


# Header of a rejection block. Real USPTO office actions vary widely on the boilerplate:
#   "Claims 1-4 are rejected under 35 U.S.C. § 103 ..."
#   "Claims 33-36 rejected under 35 U.S.C. 112(b) ..."        (no "is/are", no § symbol)
#   "Claim(s) 21-24, 33-36 is/are rejected under 35 U.S.C. 102(a)(1) ..."  (literal "(s)" and "is/are")
# The claim spec is captured lazily up to "rejected" so ranges, comma-lists, and "and" all fall
# inside group(1); the connective verb (is/are/is-are/was/were) is optional.
_REJECTION_HEADER_RE = re.compile(
    r"Claims?(?:\(s\))?\s+([\d,\s–and-]+?)\s+"
    r"(?:is/are\s+|is\s+|are\s+|was\s+|were\s+)?rejected\s+under\s+"
    r"35\s*U\.?S\.?C\.?\s*§*\s*(\d{3})",
    re.IGNORECASE,
)


def parse_claim_numbers(spec: str) -> list[int]:
    """Expand a claim spec like ``"1-4, 7 and 9-11"`` into ``[1,2,3,4,7,9,10,11]``."""
    normalized = spec.replace("–", "-")  # en-dash → hyphen
    normalized = re.sub(r"\band\b", ",", normalized, flags=re.IGNORECASE)
    numbers: set[int] = set()
    for part in normalized.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, _, hi = part.partition("-")
            if lo.strip().isdigit() and hi.strip().isdigit():
                numbers.update(range(int(lo), int(hi) + 1))
        elif part.isdigit():
            numbers.add(int(part))
    return sorted(numbers)


def _basis_from_section(section: str, following: str) -> RejectionBasis | None:
    """Resolve the statutory basis from the captured § number plus a window of trailing text."""
    section = section.strip()
    simple = {
        "101": RejectionBasis.SEC_101,
        "102": RejectionBasis.SEC_102,
        "103": RejectionBasis.SEC_103,
    }
    if section in simple:
        return simple[section]
    if section == "112":
        window = following[:80].lower()
        if "(a)" in window or "first paragraph" in window or "written description" in window or "enablement" in window:
            return RejectionBasis.SEC_112_A
        if "(b)" in window or "second paragraph" in window or "indefinite" in window or "definite" in window:
            return RejectionBasis.SEC_112_B
        return RejectionBasis.SEC_112_B  # § 112 most commonly indefiniteness in prosecution
    return None


def extract_rejections(text: str) -> list[ClaimRejection]:
    """Deterministically extract per-claim rejections, expanding grouped/range headers.

    A claim rejected under more than one statute appears once per basis. References are scoped to
    the text span of each rejection block so a claim's cited art is attributed to the right block.
    """
    matches = list(_REJECTION_HEADER_RE.finditer(text))
    rejections: list[ClaimRejection] = []
    for i, m in enumerate(matches):
        following = text[m.end() : m.end() + 120]
        basis = _basis_from_section(m.group(2), following)
        if basis is None:
            continue
        claim_numbers = parse_claim_numbers(m.group(1))
        if not claim_numbers:
            continue
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block_refs = extract_cited_references(text[m.start() : block_end])
        lowest = min(claim_numbers)
        for claim_number in claim_numbers:
            rejections.append(
                ClaimRejection(
                    claim_number=claim_number,
                    rejection_basis=basis,
                    # Heuristic: the lowest claim in a block is usually the independent one.
                    # Corrected later when the actual patent claims are retrieved.
                    is_independent=(claim_number == lowest),
                    cited_references=block_refs,
                )
            )
    return rejections


def parse_scaffold(
    text: str,
    application_number: str | None = None,
    rejection_type: str | None = None,
) -> OfficeActionAnalysis:
    """Regex-only structured scaffold. Deterministic and offline-safe.

    ``rejection_type`` overrides text-based detection — pass it when the authoritative document
    code is known (CTNF→non-final, CTFR→final, CTAV→advisory).
    """
    app_no = application_number or _first(_APP_NO_RE, text) or "UNKNOWN"
    rejections = extract_rejections(text)
    return OfficeActionAnalysis(
        application_number=app_no,
        examiner_name=_first(_EXAMINER_RE, text),
        art_unit=_first(_ART_UNIT_RE, text),
        mailing_date=_first(_MAIL_DATE_RE, text) or "",
        rejection_type=rejection_type or _detect_rejection_type(text),
        rejections=rejections,
        raw_text=text,
        # Bases recorded as flags for any rejection text the block parser didn't structure.
        unverified_claims=[f"§{b.value} rejection detected" for b in detect_bases(text)],
        # Deterministic structure raises confidence above a bare metadata-only scaffold.
        confidence_score=0.6 if rejections else 0.4,
    )


def parse(
    text: str,
    application_number: str | None = None,
    use_llm: bool = True,
    rejection_type: str | None = None,
) -> OfficeActionAnalysis:
    """Parse OA text into an ``OfficeActionAnalysis``.

    With ``use_llm=True`` and a configured Anthropic key, the claim→limitation→reference
    mappings are filled in by the analyzer pipeline. Otherwise returns the regex scaffold.
    """
    scaffold = parse_scaffold(text, application_number, rejection_type=rejection_type)
    if not use_llm:
        return scaffold
    try:
        # Imported lazily to avoid a hard dependency on the LLM client for offline parsing.
        from src.generation.oa_analyzer import structure_office_action

        return structure_office_action(text, scaffold)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully to the scaffold
        logger.warning("LLM structuring unavailable (%s); returning regex scaffold.", exc)
        return scaffold
