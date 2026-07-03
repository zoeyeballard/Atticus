"""Vector store facade.

Thin wrapper that pairs the embedding model with the configured storage backend
(``src/db/backends.py``). All raw database access lives in the backend — this module never
imports psycopg. Public API (``init_schema``, ``upsert``, ``search``, ``count``) is unchanged so
retrievers and seed scripts are unaffected by the backend swap.
"""

from __future__ import annotations

from src.config import get_settings
from src.db.backends import SearchHit, VectorBackend, get_vector_backend
from src.retrieval.embeddings import Embedder

__all__ = ["VectorStore", "SearchHit"]


class VectorStore:
    """Embeddings + a pluggable vector backend."""

    def __init__(self, embedder: Embedder | None = None, backend: VectorBackend | None = None) -> None:
        self.embedder = embedder or Embedder()
        self.backend = backend or get_vector_backend()

    def init_schema(self) -> None:
        self.backend.init_schema()

    def upsert(
        self,
        document_id: str,
        text: str,
        metadata: dict | None = None,
        chunk_index: int = 0,
        embedding: list[float] | None = None,
    ) -> None:
        vector = embedding if embedding is not None else self.embedder.embed(text)
        self.backend.upsert(
            document_id=document_id,
            text=text,
            metadata=metadata,
            chunk_index=chunk_index,
            embedding=vector,
        )

    def search(
        self, query: str, top_k: int | None = None, filters: dict | None = None
    ) -> list[SearchHit]:
        top_k = top_k or get_settings().default_top_k
        return self.backend.search(self.embedder.embed(query), top_k=top_k, filters=filters)

    def count(self, filters: dict | None = None) -> int:
        return self.backend.count(filters=filters)
