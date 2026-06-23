-- Atticus initial schema. Loaded by docker-entrypoint-initdb.d on first DB start.

CREATE EXTENSION IF NOT EXISTS vector;

-- Document chunks for closed-loop retrieval (patents + MPEP).
CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    document_id  TEXT NOT NULL,
    chunk_index  INT  NOT NULL DEFAULT 0,
    text         TEXT NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}',
    embedding    vector(384) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_metadata_idx ON chunks USING gin (metadata);

-- Stored office-action analyses.
CREATE TABLE IF NOT EXISTS analyses (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_number TEXT NOT NULL,
    analysis           JSONB NOT NULL,
    confidence_score   REAL NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Append-only audit trail: what was retrieved, generated, verified, flagged.
CREATE TABLE IF NOT EXISTS audit_events (
    id          BIGSERIAL PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    step        TEXT NOT NULL,        -- retrieved | generated | verified | flagged
    payload     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_analysis_idx ON audit_events (analysis_id);
