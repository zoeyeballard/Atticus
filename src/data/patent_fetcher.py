"""Fetch and parse a patent into a structured ``Patent`` (claims, spec, figures, classes)."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.data.uspto_client import USPTOClient
from src.models.schemas import Patent, PatentClaim

logger = logging.getLogger(__name__)

# A claim begins with its number; dependent claims reference a parent claim.
_CLAIM_SPLIT_RE = re.compile(r"(?m)^\s*(\d{1,3})\s*\.\s+")
_DEPENDS_RE = re.compile(r"\bclaim\s+(\d{1,3})\b", re.IGNORECASE)


def parse_claims(claims_text: str) -> list[PatentClaim]:
    """Split a block of claim text into individual ``PatentClaim`` objects."""
    parts = _CLAIM_SPLIT_RE.split(claims_text)
    # split() yields [pre, num1, body1, num2, body2, ...]
    claims: list[PatentClaim] = []
    for i in range(1, len(parts) - 1, 2):
        number = int(parts[i])
        body = parts[i + 1].strip()
        depends_match = _DEPENDS_RE.search(body[:120])
        depends_on = int(depends_match.group(1)) if depends_match else None
        claims.append(
            PatentClaim(
                number=number,
                text=body,
                is_independent=depends_on is None,
                depends_on=depends_on,
            )
        )
    return claims


def _patent_from_payload(patent_number: str, payload: dict[str, Any]) -> Patent:
    claims_text = payload.get("claims") or payload.get("claimsText") or ""
    return Patent(
        patent_number=patent_number,
        publication_number=payload.get("publicationNumber"),
        title=payload.get("inventionTitle") or payload.get("title"),
        first_named_inventor=payload.get("firstNamedInventor", ""),
        abstract=payload.get("abstractText") or payload.get("abstract"),
        claims=parse_claims(claims_text) if isinstance(claims_text, str) else [],
        specification=payload.get("descriptionText") or payload.get("specification"),
        classification_codes=payload.get("cpcClassifications", []) or payload.get("classes", []),
        figures=payload.get("figures", []),
    )


def fetch_patent(patent_number: str, client: USPTOClient | None = None) -> Patent:
    """Fetch a patent by number and parse it into a ``Patent`` model."""
    owns_client = client is None
    client = client or USPTOClient()
    try:
        payload = client.get_patent_full_text(patent_number)
        return _patent_from_payload(patent_number, payload)
    finally:
        if owns_client:
            client.close()
