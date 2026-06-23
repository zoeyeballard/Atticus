"""Fetch sample patents for TC 2100/2600 and index their chunks.

Usage: python scripts/seed_sample_patents.py US9876543 US10234567 ...

Chunks each patent by claim (one chunk per claim) and indexes them in pgvector for prior-art
retrieval. Requires USPTO_API_KEY.
"""

from __future__ import annotations

import logging
import sys

from src.data.patent_fetcher import fetch_patent
from src.retrieval.vector_store import VectorStore

logging.basicConfig(level="INFO")
logger = logging.getLogger("seed_patents")


def main(patent_numbers: list[str]) -> None:
    if not patent_numbers:
        logger.error("Provide at least one patent number, e.g. US9876543")
        sys.exit(1)

    store = VectorStore()
    store.init_schema()

    for number in patent_numbers:
        try:
            patent = fetch_patent(number)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch %s: %s", number, exc)
            continue
        for claim in patent.claims:
            store.upsert(
                document_id=f"{patent.patent_number}:claim:{claim.number}",
                text=claim.text,
                metadata={
                    "document_type": "patent",
                    "patent_number": patent.patent_number,
                    "title": patent.title or "",
                    "claim_number": claim.number,
                    "is_independent": claim.is_independent,
                },
                chunk_index=claim.number,
            )
        logger.info("Indexed %s (%d claims)", patent.patent_number, len(patent.claims))


if __name__ == "__main__":
    main(sys.argv[1:])
