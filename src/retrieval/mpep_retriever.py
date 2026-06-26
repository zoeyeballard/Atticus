"""Retrieve relevant MPEP sections from the vector store."""

from __future__ import annotations

from src.config import get_settings
from src.models.schemas import PriorArtSearchResult
from src.retrieval.vector_store import VectorStore


class MPEPRetriever:
    """Top-k retrieval over indexed MPEP chunks."""

    def __init__(self, vector_store: VectorStore | None = None) -> None:
        self.vector_store = vector_store or VectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        chapter: str | None = None,
    ) -> list[PriorArtSearchResult]:
        top_k = top_k or get_settings().default_top_k
        filters: dict = {"document_type": "mpep"}
        if chapter:
            filters["chapter"] = chapter
        hits = self.vector_store.search(query, top_k=top_k, filters=filters)
        return [
            PriorArtSearchResult(
                patent_number=hit.metadata.get("section", hit.document_id),
                title=hit.metadata.get("title"),
                relevance_score=hit.score,
                matched_chunk=hit.text,
                document_type="mpep",
                metadata=hit.metadata,
            )
            for hit in hits
        ]

    # Natural-language alias used throughout the docs/verification snippets.
    def search(self, query: str, top_k: int | None = None) -> list[PriorArtSearchResult]:
        return self.retrieve(query, top_k=top_k)

    def count(self) -> int:
        """Number of indexed MPEP chunks."""
        return self.vector_store.count(filters={"document_type": "mpep"})
