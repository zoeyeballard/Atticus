"""Download and index MPEP chapters relevant to TC 2100/2600.

Usage:
    python scripts/seed_mpep.py                     # chapters 700, 2100, 2200
    python scripts/seed_mpep.py --chapter 2100
    python scripts/seed_mpep.py --source-dir data/mpep   # index pre-downloaded .txt files

Resolution order per chapter:
  1. A local ``<source-dir>/<chapter>.txt`` file, if present (fastest, deterministic).
  2. Otherwise, a best-effort HTTP download from the USPTO MPEP HTML, cached to that path.

Priority subsections to confirm after seeding (see NEXT_STEPS.md Step 4):
  § 2141–2145 (Graham/§103), § 2143 (KSR rationales), § 2106 (Alice/Mayo/§101),
  § 2161–2163 (§112 written description/enablement), § 714 (responses), § 706 (rejections).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from pathlib import Path

from src.data.mpep_indexer import RELEVANT_CHAPTERS, index_mpep
from src.retrieval.vector_store import VectorStore

logging.basicConfig(level="INFO")
logger = logging.getLogger("seed_mpep")

# Override with MPEP_BASE_URL if the USPTO path structure differs.
_DEFAULT_MPEP_URL = "https://www.uspto.gov/web/offices/pac/mpep/mpep-{chapter}.html"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def _html_to_text(html: str) -> str:
    """Crude HTML → text: drop script/style, strip tags, collapse whitespace."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = _TAG_RE.sub(" ", html)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    )
    lines = [_WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _download_chapter(chapter: str, dest: Path) -> str | None:
    """Best-effort download of one MPEP chapter to ``dest``; returns text or None on failure."""
    import httpx

    url = os.environ.get("MPEP_BASE_URL", _DEFAULT_MPEP_URL).format(chapter=chapter)
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not download MPEP chapter %s from %s: %s", chapter, url, exc)
        return None
    text = _html_to_text(resp.text)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    logger.info("Downloaded MPEP chapter %s (%d chars) → %s", chapter, len(text), dest)
    return text


def _load_chapter(chapter: str, source_dir: Path) -> str | None:
    path = source_dir / f"{chapter}.txt"
    if path.exists():
        return path.read_text("utf-8")
    return _download_chapter(chapter, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Index MPEP chapters into pgvector.")
    parser.add_argument("--chapter", action="append", default=None, help="MPEP chapter number")
    parser.add_argument(
        "--source-dir",
        default=os.environ.get("MPEP_SOURCE_DIR", "data/mpep"),
        help="Directory of <chapter>.txt files (also the download cache)",
    )
    parser.add_argument(
        "--no-download", action="store_true", help="Only index local files; never fetch"
    )
    args = parser.parse_args()

    chapters = args.chapter or RELEVANT_CHAPTERS
    source_dir = Path(args.source_dir)
    store = VectorStore()
    store.init_schema()

    total = 0
    for chapter in chapters:
        if args.no_download:
            path = source_dir / f"{chapter}.txt"
            text = path.read_text("utf-8") if path.exists() else None
        else:
            text = _load_chapter(chapter, source_dir)
        if not text:
            logger.warning("No content for chapter %s — skipping", chapter)
            continue
        total += index_mpep(text, revision="local", vector_store=store)
    logger.info("Done. Indexed %d MPEP chunks across chapters %s.", total, chapters)


if __name__ == "__main__":
    main()
