"""Retrieve relevant patents / prior art from the vector store."""

from __future__ import annotations

from src.config import get_settings
from src.models.schemas import PriorArtSearchResult
from src.retrieval.query_reformulator import reformulate
from src.retrieval.vector_store import VectorStore


class PatentRetriever:
    """Top-k retrieval over indexed patent chunks, with query reformulation."""

    def __init__(self, vector_store: VectorStore | None = None) -> None:
        self.vector_store = vector_store or VectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        is_claim_limitation: bool = False,
        filters: dict | None = None,
    ) -> list[PriorArtSearchResult]:
        top_k = top_k or get_settings().default_top_k
        reformulated = reformulate(query, is_claim_limitation=is_claim_limitation)
        search_filters = {"document_type": "patent", **(filters or {})}
        hits = self.vector_store.search(reformulated, top_k=top_k, filters=search_filters)
        return [
            PriorArtSearchResult(
                patent_number=hit.metadata.get("patent_number", hit.document_id),
                title=hit.metadata.get("title"),
                relevance_score=hit.score,
                matched_chunk=hit.text,
                document_type="patent",
                metadata=hit.metadata,
            )
            for hit in hits
        ]
