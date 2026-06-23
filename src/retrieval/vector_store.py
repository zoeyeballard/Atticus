"""pgvector-backed vector store.

Stores document chunks with their embeddings and metadata in PostgreSQL, and performs cosine
similarity search with optional metadata filtering (hybrid search). All chunks carry a
``document_id`` and ``document_type`` so retrieved context can always be traced back to a
verified source — the foundation of closed-loop retrieval.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from src.config import get_settings
from src.retrieval.embeddings import Embedder

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    document_id: str
    text: str
    score: float
    metadata: dict


_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    document_id  TEXT NOT NULL,
    chunk_index  INT  NOT NULL DEFAULT 0,
    text         TEXT NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}',
    embedding    vector(%(dim)s) NOT NULL,
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_metadata_idx ON chunks USING gin (metadata);
"""


class VectorStore:
    """pgvector operations: schema init, upsert, and similarity search."""

    def __init__(self, dsn: str | None = None, embedder: Embedder | None = None) -> None:
        self.dsn = dsn or get_settings().database_url
        self.embedder = embedder or Embedder()
        self.dim = get_settings().embedding_dim

    def _connect(self):
        import psycopg  # deferred so the module imports without a live DB
        from pgvector.psycopg import register_vector

        conn = psycopg.connect(self.dsn)
        register_vector(conn)
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_SCHEMA % {"dim": self.dim})
            conn.commit()

    def upsert(
        self,
        document_id: str,
        text: str,
        metadata: dict | None = None,
        chunk_index: int = 0,
        embedding: list[float] | None = None,
    ) -> None:
        vector = embedding if embedding is not None else self.embedder.embed(text)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunks (document_id, chunk_index, text, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (document_id, chunk_index)
                DO UPDATE SET text = EXCLUDED.text,
                              metadata = EXCLUDED.metadata,
                              embedding = EXCLUDED.embedding
                """,
                (document_id, chunk_index, text, json.dumps(metadata or {}), vector),
            )
            conn.commit()

    def search(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict | None = None,
    ) -> list[SearchHit]:
        """Cosine-similarity search with optional exact-match metadata filters."""
        top_k = top_k or get_settings().default_top_k
        query_vec = self.embedder.embed(query)

        where = ""
        params: list = [query_vec]
        if filters:
            clauses = []
            for key, value in filters.items():
                clauses.append("metadata ->> %s = %s")
                params.extend([key, str(value)])
            where = "WHERE " + " AND ".join(clauses)
        params.append(top_k)

        sql = f"""
            SELECT document_id, text, metadata, 1 - (embedding <=> %s) AS score
            FROM chunks
            {where}
            ORDER BY embedding <=> %s
            LIMIT %s
        """
        # The ORDER BY needs the query vector too; insert it before LIMIT.
        params.insert(-1, query_vec)

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [
            SearchHit(document_id=r[0], text=r[1], metadata=r[2], score=float(r[3]))
            for r in rows
        ]
