"""Download and index MPEP chapters relevant to TC 2100/2600.

Usage: python scripts/seed_mpep.py [--chapter 2100 ...]

This is a scaffold: it wires together the indexer and vector store. Point ``MPEP_SOURCE_DIR`` at
local MPEP text files (one per chapter) to index them. Network download of the official MPEP is
left as a follow-up (the USPTO publishes it as PDF/HTML).
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from src.data.mpep_indexer import RELEVANT_CHAPTERS, index_mpep
from src.retrieval.vector_store import VectorStore

logging.basicConfig(level="INFO")
logger = logging.getLogger("seed_mpep")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index MPEP chapters into pgvector.")
    parser.add_argument("--chapter", action="append", default=None, help="MPEP chapter number")
    parser.add_argument(
        "--source-dir",
        default=os.environ.get("MPEP_SOURCE_DIR", "data/mpep"),
        help="Directory of <chapter>.txt files",
    )
    args = parser.parse_args()

    chapters = args.chapter or RELEVANT_CHAPTERS
    source_dir = Path(args.source_dir)
    store = VectorStore()
    store.init_schema()

    total = 0
    for chapter in chapters:
        path = source_dir / f"{chapter}.txt"
        if not path.exists():
            logger.warning("Missing %s — skipping chapter %s", path, chapter)
            continue
        total += index_mpep(path.read_text("utf-8"), revision="local", vector_store=store)
    logger.info("Done. Indexed %d MPEP chunks across chapters %s.", total, chapters)


if __name__ == "__main__":
    main()
