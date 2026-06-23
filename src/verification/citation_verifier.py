"""Verify citations: patent numbers, patent passages, and MPEP sections.

A patent number that does not exist in USPTO is the clearest hallucination signal, so existence
checks run first and short-circuit to FABRICATED. Passage-level claims are then checked by the
entailment checker.
"""

from __future__ import annotations

import logging
import re

from src.data.uspto_client import USPTOClient
from src.models.schemas import VerificationStatus, VerifiedClaim

logger = logging.getLogger(__name__)

_PATENT_RE = re.compile(r"US[\s-]?[\d,]{7,12}|US\d{4}/\d{6,7}|\b\d{1,2},\d{3},\d{3}\b")
_MPEP_RE = re.compile(r"MPEP\s*§?\s*(\d{3,4}(?:\.\d{1,2})*)", re.IGNORECASE)


def extract_patent_numbers(text: str) -> list[str]:
    # Normalize to a canonical form (no whitespace, no thousands separators) so downstream
    # existence checks and substring comparisons are consistent.
    return [re.sub(r"[\s,]", "", m.group(0)) for m in _PATENT_RE.finditer(text)]


def extract_mpep_sections(text: str) -> list[str]:
    return [m.group(1) for m in _MPEP_RE.finditer(text)]


def verify_citation(
    claim_text: str,
    claim_type: str,
    uspto: USPTOClient | None = None,
    known_mpep_sections: set[str] | None = None,
) -> VerifiedClaim:
    """Verify a single citation-bearing claim.

    Existence checks only — characterization (does the source *say* what was claimed) is the job
    of the entailment checker, which this composes with in ``hallucination_detector``.
    """
    owns_client = uspto is None
    uspto = uspto or USPTOClient()
    try:
        patents = extract_patent_numbers(claim_text)
        for number in patents:
            if not uspto.patent_exists(number):
                return VerifiedClaim(
                    claim_text=claim_text,
                    claim_type=claim_type,
                    status=VerificationStatus.FABRICATED,
                    source_document=number,
                    confidence=0.95,
                    explanation=f"Patent {number} not found in USPTO records.",
                )

        if known_mpep_sections is not None:
            for section in extract_mpep_sections(claim_text):
                if section not in known_mpep_sections:
                    return VerifiedClaim(
                        claim_text=claim_text,
                        claim_type=claim_type,
                        status=VerificationStatus.FABRICATED,
                        source_document=f"MPEP {section}",
                        confidence=0.9,
                        explanation=f"MPEP §{section} not found in the indexed corpus.",
                    )

        if patents or extract_mpep_sections(claim_text):
            return VerifiedClaim(
                claim_text=claim_text,
                claim_type=claim_type,
                status=VerificationStatus.VERIFIED,
                source_document=patents[0] if patents else None,
                confidence=0.8,
                explanation="Cited source(s) exist; characterization pending entailment check.",
            )

        return VerifiedClaim(
            claim_text=claim_text,
            claim_type=claim_type,
            status=VerificationStatus.UNVERIFIABLE,
            confidence=0.3,
            explanation="No citation found in claim to verify.",
        )
    finally:
        if owns_client:
            uspto.close()
