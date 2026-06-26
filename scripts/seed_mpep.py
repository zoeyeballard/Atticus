"""Download and index priority MPEP sections into pgvector.

Usage:
    python scripts/seed_mpep.py                 # all priority sections
    python scripts/seed_mpep.py --section 2143  # one section

The USPTO publishes the MPEP as per-section HTML pages at
``https://www.uspto.gov/web/offices/pac/mpep/s<NNNN>.html`` (the chapter-level pages are just
tables of contents). We fetch the prosecution-relevant sections, strip HTML to text, chunk each
section to ~500 tokens without splitting paragraphs, embed locally with sentence-transformers
($0), and upsert into the ``chunks`` table with ``document_type=mpep`` metadata.

Pages are cached under ``data/mpep/<section>.html`` so re-runs are offline.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from src.data.mpep_indexer import chunk_section
from src.retrieval.vector_store import VectorStore

logging.basicConfig(level="INFO")
logger = logging.getLogger("seed_mpep")

_SECTION_URL = "https://www.uspto.gov/web/offices/pac/mpep/s{section}.html"
_UA = {"User-Agent": "Mozilla/5.0 (Atticus patent-prosecution research prototype)"}

# Prosecution-relevant MPEP sections (Phase 2 priorities), section -> (chapter, title).
PRIORITY_SECTIONS: dict[str, tuple[str, str]] = {
    "706": ("700", "Rejection of Claims"),
    "714": ("700", "Amendments and Other Replies"),
    "2106": ("2100", "Patent Subject Matter Eligibility (Alice/Mayo)"),
    "2111": ("2100", "Claim Interpretation; Broadest Reasonable Interpretation"),
    "2131": ("2100", "Anticipation — Application of 35 U.S.C. 102"),
    "2141": ("2100", "Examination Guidelines for Obviousness (35 U.S.C. 103)"),
    "2143": ("2100", "Examples of Rationales (KSR) for Obviousness"),
    "2161": ("2100", "Written Description and Enablement (35 U.S.C. 112)"),
    "2163": ("2100", "Written Description Requirement"),
    "2201": ("2200", "Introduction — Citation of Prior Art and Reexamination"),
}

_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_text(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"</(p|div|li|h[1-6]|tr|br\s*/?)>", "\n\n", html, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", html)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
        .replace("&gt;", ">").replace("&#167;", "§").replace("&sect;", "§")
    )
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _load_section(section: str, cache_dir: Path, allow_download: bool) -> str | None:
    path = cache_dir / f"{section}.html"
    if path.exists():
        return _html_to_text(path.read_text("utf-8"))
    if not allow_download:
        return None
    import httpx

    url = _SECTION_URL.format(section=section)
    for attempt in range(3):
        try:
            r = httpx.get(url, headers=_UA, timeout=30, follow_redirects=True)
            r.raise_for_status()
            cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(r.text, encoding="utf-8")
            return _html_to_text(r.text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("MPEP §%s download attempt %d failed: %s", section, attempt + 1, exc)
            time.sleep(2 * (attempt + 1))
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Index priority MPEP sections into pgvector.")
    parser.add_argument("--section", action="append", default=None, help="MPEP section number")
    parser.add_argument("--source-dir", default=os.environ.get("MPEP_SOURCE_DIR", "data/mpep"))
    parser.add_argument("--no-download", action="store_true", help="Only index cached pages")
    args = parser.parse_args()

    sections = args.section or list(PRIORITY_SECTIONS)
    cache_dir = Path(args.source_dir)
    store = VectorStore()
    store.init_schema()

    total = 0
    indexed_sections = []
    for section in sections:
        chapter, title = PRIORITY_SECTIONS.get(section, ("", f"MPEP {section}"))
        text = _load_section(section, cache_dir, allow_download=not args.no_download)
        if not text or len(text) < 500:
            logger.warning("§%s: no usable content — skipping", section)
            continue
        chunks = chunk_section(section, title, text, chapter=chapter)
        for chunk in chunks:
            store.upsert(
                document_id=f"mpep:{section}",
                chunk_index=chunk.metadata["chunk_index"],
                text=chunk.text,
                metadata=chunk.to_metadata(),
            )
        total += len(chunks)
        indexed_sections.append(section)
        logger.info("§%s (%s): %d chunks", section, title, len(chunks))

    logger.info("Done. Indexed %d chunks across sections %s.", total, indexed_sections)


if __name__ == "__main__":
    main()
