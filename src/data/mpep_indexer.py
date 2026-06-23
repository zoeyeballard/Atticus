"""Index MPEP sections for retrieval.

Chunks MPEP text by section/subsection while preserving the chapter → section → subsection
hierarchy as metadata, then hands chunks to the vector store. We focus on the chapters most
relevant to TC 2100/2600 prosecution: 700 (examination), 2100 (patentability), 2200 (citation
of prior art).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

RELEVANT_CHAPTERS = ["700", "2100", "2200"]

# MPEP section headers look like "2143.01   Suggestion or Motivation To Modify the References"
_SECTION_RE = re.compile(r"(?m)^\s*(\d{3,4}(?:\.\d{1,2})*)\s+([A-Z][^\n]{3,120})$")


@dataclass
class MPEPChunk:
    """One retrievable MPEP chunk plus its hierarchy metadata."""

    section: str  # e.g. "2143.01"
    title: str
    text: str
    chapter: str = ""
    revision: str = ""
    metadata: dict = field(default_factory=dict)

    def to_metadata(self) -> dict:
        return {
            "document_type": "mpep",
            "section": self.section,
            "title": self.title,
            "chapter": self.chapter or self.section.split(".")[0][:2] + "00",
            "revision": self.revision,
            **self.metadata,
        }


def chunk_mpep(text: str, revision: str = "") -> list[MPEPChunk]:
    """Split raw MPEP text into per-section chunks."""
    matches = list(_SECTION_RE.finditer(text))
    chunks: list[MPEPChunk] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        section = m.group(1)
        chunks.append(
            MPEPChunk(
                section=section,
                title=m.group(2).strip(),
                text=body,
                chapter=section.split(".")[0][:2] + "00",
                revision=revision,
            )
        )
    return chunks


def index_mpep(text: str, revision: str = "", vector_store=None) -> int:
    """Chunk MPEP text and upsert chunks into the vector store.

    Returns the number of chunks indexed. If ``vector_store`` is None this only chunks (useful
    for tests / dry runs).
    """
    chunks = chunk_mpep(text, revision)
    if vector_store is not None:
        for chunk in chunks:
            vector_store.upsert(
                document_id=f"mpep:{chunk.section}",
                text=chunk.text,
                metadata=chunk.to_metadata(),
            )
    logger.info("Indexed %d MPEP chunks (revision=%s)", len(chunks), revision or "unknown")
    return len(chunks)
