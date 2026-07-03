"""Storage backend abstraction.

All raw database access lives under ``src/db/`` behind these interfaces so the rest of the
codebase never imports psycopg or writes SQL directly. This keeps the desktop path open: a future
``SqliteVecBackend`` can satisfy ``VectorBackend`` without touching retrieval/generation code.

Config selects the backend via ``STORAGE_BACKEND`` (``postgres`` today; ``sqlite`` reserved for
the desktop build).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.config import get_settings


@dataclass
class SearchHit:
    document_id: str
    text: str
    score: float
    metadata: dict


class VectorBackend(ABC):
    """Abstract vector storage. Implementations: PgVectorBackend (now), SqliteVecBackend (later)."""

    @abstractmethod
    def init_schema(self) -> None: ...

    @abstractmethod
    def upsert(
        self,
        document_id: str,
        text: str,
        metadata: dict | None = None,
        chunk_index: int = 0,
        embedding: list[float] | None = None,
    ) -> None: ...

    @abstractmethod
    def search(
        self, query_embedding: list[float], top_k: int, filters: dict | None = None
    ) -> list[SearchHit]: ...

    @abstractmethod
    def count(self, filters: dict | None = None) -> int: ...


class StorageBackend(ABC):
    """Abstract relational storage for client data (analyses/drafts/audit).

    The prototype uses an in-memory repository (``src/db/repositories.py``); a Postgres-backed
    implementation of this interface is the production path. Defined here so the boundary is
    explicit and nothing outside ``src/db/`` reaches for a connection.
    """

    @abstractmethod
    def execute(self, sql: str, params: list | None = None) -> list[tuple]: ...


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


class PgVectorBackend(VectorBackend):
    """PostgreSQL + pgvector implementation."""

    def __init__(self, dsn: str | None = None, dim: int | None = None) -> None:
        settings = get_settings()
        self.dsn = dsn or settings.database_url
        self.dim = dim or settings.embedding_dim

    def _connect(self):
        import psycopg
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
                (document_id, chunk_index, text, json.dumps(metadata or {}), embedding),
            )
            conn.commit()

    def _where(self, filters: dict | None) -> tuple[str, list]:
        if not filters:
            return "", []
        clauses, params = [], []
        for key, value in filters.items():
            clauses.append("metadata ->> %s = %s")
            params.extend([key, str(value)])
        return "WHERE " + " AND ".join(clauses), params

    def count(self, filters: dict | None = None) -> int:
        where, params = self._where(filters)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM chunks {where}", params)
            return int(cur.fetchone()[0])

    def search(
        self, query_embedding: list[float], top_k: int, filters: dict | None = None
    ) -> list[SearchHit]:
        # Bind the query vector as a pgvector literal so the cosine operator gets a `vector`.
        vec_literal = "[" + ",".join(repr(float(x)) for x in query_embedding) + "]"
        where, where_params = self._where(filters)
        params = [vec_literal, *where_params, vec_literal, top_k]
        sql = f"""
            SELECT document_id, text, metadata, 1 - (embedding <=> %s::vector) AS score
            FROM chunks
            {where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [
            SearchHit(document_id=r[0], text=r[1], metadata=r[2], score=float(r[3])) for r in rows
        ]


def get_vector_backend() -> VectorBackend:
    """Return the configured vector backend (``postgres`` by default)."""
    backend = get_settings().storage_backend
    if backend == "postgres":
        return PgVectorBackend()
    raise NotImplementedError(
        f"STORAGE_BACKEND={backend!r} is reserved for the desktop build; only 'postgres' is "
        "implemented. See Phase 3 roadmap R1 (SQLite + sqlite-vec)."
    )
