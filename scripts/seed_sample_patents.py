"""Index real patent text into pgvector for prior-art retrieval.

Usage:
    python scripts/seed_sample_patents.py                 # the apps in data/test_applications.json
    python scripts/seed_sample_patents.py 19531961 19406513

For each application, downloads its own claims (CLM), specification (SPEC), and abstract (ABST)
documents from the USPTO ODP, extracts text, chunks it (claims one-per-claim; spec by paragraph),
embeds locally with sentence-transformers ($0), and upserts into the ``chunks`` table with
``document_type=patent`` metadata.

Note on cited references: the ODP granted-patent full-text endpoint (`/patent/grants/{n}/full-text`)
returns 403 with a standard data.uspto.gov key, so we index the application's own text (the
invention under examination) via the working documents+download path. Indexing the examiner's
cited references would need elevated ODP access or a separate full-text source.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from src.data.patent_fetcher import parse_claims
from src.data.uspto_client import USPTOClient, USPTOError
from src.data.mpep_indexer import chunk_section  # paragraph-aware chunker (reused for spec)
from src.retrieval.vector_store import VectorStore

logging.basicConfig(level="INFO")
logger = logging.getLogger("seed_patents")


def _default_apps() -> list[str]:
    registry = Path("data/test_applications.json")
    if registry.exists():
        return [a["application_number"] for a in json.loads(registry.read_text())]
    return []


def seed_application(app: str, client: USPTOClient, store: VectorStore) -> int:
    """Index one application's claims, specification, and abstract. Returns chunk count."""
    count = 0
    meta = client.get_application(app).get("applicationMetaData", {})
    title = meta.get("inventionTitle") or meta.get("inventionTitleText")

    # Claims: one chunk per claim.
    try:
        claims = parse_claims(client.get_document_text(app, "CLM"))
        for claim in claims:
            store.upsert(
                document_id=f"{app}:claim:{claim.number}",
                chunk_index=claim.number,
                text=claim.text,
                metadata={
                    "document_type": "patent",
                    "patent_number": app,
                    "title": title,
                    "section_type": "claims",
                    "claim_number": claim.number,
                    "is_independent": claim.is_independent,
                },
            )
        count += len(claims)
        logger.info("%s: %d claims", app, len(claims))
    except USPTOError as exc:
        logger.warning("%s: claims unavailable (%s)", app, exc)

    # Specification: paragraph-aware chunks.
    try:
        spec_chunks = chunk_section(app, title or app, client.get_document_text(app, "SPEC"))
        for i, ch in enumerate(spec_chunks):
            store.upsert(
                document_id=f"{app}:spec:{i}",
                chunk_index=i,
                text=ch.text,
                metadata={
                    "document_type": "patent",
                    "patent_number": app,
                    "title": title,
                    "section_type": "specification",
                    "chunk_index": i,
                },
            )
        count += len(spec_chunks)
        logger.info("%s: %d spec chunks", app, len(spec_chunks))
    except USPTOError as exc:
        logger.warning("%s: spec unavailable (%s)", app, exc)

    # Abstract: single chunk.
    try:
        abstract = client.get_document_text(app, "ABST").strip()
        if abstract:
            store.upsert(
                document_id=f"{app}:abstract",
                chunk_index=0,
                text=abstract,
                metadata={
                    "document_type": "patent",
                    "patent_number": app,
                    "title": title,
                    "section_type": "abstract",
                },
            )
            count += 1
    except USPTOError as exc:
        logger.warning("%s: abstract unavailable (%s)", app, exc)

    return count


def main(apps: list[str]) -> None:
    apps = apps or _default_apps()
    if not apps:
        logger.error("No applications given and data/test_applications.json is empty.")
        sys.exit(1)

    store = VectorStore()
    store.init_schema()
    total = 0
    for app in apps:
        with USPTOClient() as client:
            try:
                total += seed_application(app, client, store)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to seed %s: %s", app, exc)
    logger.info("Done. Indexed %d patent chunks across %d application(s).", total, len(apps))


if __name__ == "__main__":
    main(sys.argv[1:])
