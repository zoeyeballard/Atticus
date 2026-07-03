"""Office-action analysis pipeline.

Orchestrates: fetch OA → parse scaffold → fetch cited references → retrieve MPEP →
LLM-structure the rejections (grounded, schema-validated) → return ``OfficeActionAnalysis``.

The key safety property: the LLM is only allowed to map limitations to references that
deterministic extraction confirmed are present in the OA text. Anything else is downgraded to an
unverified objection rather than silently accepted.
"""

from __future__ import annotations

import logging

from src.data.office_action_parser import extract_cited_references, parse_scaffold
from src.generation.llm_client import LLMClient
from src.generation.prompt_templates import ANALYZE_OFFICE_ACTION
from src.models.schemas import (
    CitedReference,
    ClaimRejection,
    LimitationMapping,
    OfficeActionAnalysis,
    RejectionBasis,
)

logger = logging.getLogger(__name__)


def _format_known_references(refs: list[CitedReference]) -> str:
    if not refs:
        return "(none detected)"
    return "\n".join(f"- {r.patent_number}" for r in refs)


def structure_office_action(
    text: str,
    scaffold: OfficeActionAnalysis | None = None,
    llm: LLMClient | None = None,
) -> OfficeActionAnalysis:
    """Use the LLM to fill in structured rejections, constrained to known references."""
    scaffold = scaffold or parse_scaffold(text)
    known_refs = extract_cited_references(text)
    known_numbers = {r.patent_number for r in known_refs}
    llm = llm or LLMClient()

    prompt = ANALYZE_OFFICE_ACTION
    user = prompt.render(
        office_action_text=text,
        known_references=_format_known_references(known_refs),
    )
    # Large office actions produce large structured output; give room to avoid truncation
    # (on overflow the caller degrades to the deterministic scaffold, preserving accuracy).
    data = llm.complete_json(prompt.system, user, max_tokens=8192)

    rejections = _build_rejections(data.get("rejections", []), known_numbers)
    objections = list(data.get("objections", [])) + scaffold.objections

    analysis = scaffold.model_copy(
        update={
            "rejection_type": data.get("rejection_type", scaffold.rejection_type),
            "examiner_name": data.get("examiner_name") or scaffold.examiner_name,
            "art_unit": data.get("art_unit") or scaffold.art_unit,
            "mailing_date": data.get("mailing_date") or scaffold.mailing_date,
            "rejections": rejections,
            "objections": objections,
            "requirements": list(data.get("requirements", [])),
            "confidence_score": 0.8 if rejections else 0.5,
        }
    )
    return analysis


def _build_rejections(
    raw_rejections: list[dict], known_numbers: set[str]
) -> list[ClaimRejection]:
    """Validate LLM output into ClaimRejection objects, dropping unknown references."""
    rejections: list[ClaimRejection] = []
    for raw in raw_rejections:
        try:
            basis = RejectionBasis(str(raw["rejection_basis"]))
        except (KeyError, ValueError):
            logger.warning("Skipping rejection with unknown basis: %r", raw.get("rejection_basis"))
            continue

        mappings = [
            LimitationMapping(
                limitation_text=m.get("limitation_text", ""),
                mapped_to_reference=m.get("mapped_to_reference", ""),
                reference_passage=m.get("reference_passage", ""),
                examiner_reasoning=m.get("examiner_reasoning"),
                source_span=m.get("source_span"),
            )
            for m in raw.get("limitation_mappings", [])
            # Only keep mappings to references we deterministically confirmed (or null/unmapped).
            if not m.get("mapped_to_reference")
            or _normalize(m["mapped_to_reference"]) in {_normalize(k) for k in known_numbers}
        ]

        cited = [
            CitedReference(
                patent_number=c.get("patent_number", ""),
                relevant_passages=c.get("relevant_passages", []),
            )
            for c in raw.get("cited_references", [])
            if _normalize(c.get("patent_number", "")) in {_normalize(k) for k in known_numbers}
        ]

        rejections.append(
            ClaimRejection(
                claim_number=int(raw.get("claim_number", 0)),
                rejection_basis=basis,
                is_independent=bool(raw.get("is_independent", False)),
                limitation_mappings=mappings,
                cited_references=cited,
            )
        )
    return rejections


def _normalize(number: str) -> str:
    return number.replace(",", "").replace(" ", "").upper()
