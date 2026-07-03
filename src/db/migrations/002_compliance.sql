-- Phase 3: legal-compliance schema (data classification + tenant isolation).
--
-- PUBLIC data (MPEP + published patents) lives in `chunks` — shared across all tenants,
-- no access controls, permanent. CLIENT work product (analyses, response_drafts,
-- audit_events) is tenant-isolated with a configurable retention window. Client data must
-- never flow back into `chunks` or the shared retrieval corpus.

CREATE TABLE IF NOT EXISTS tenants (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           TEXT NOT NULL,
    retention_days INTEGER NOT NULL DEFAULT 90,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Fixed default tenant for the single-user prototype (see src/config for the constant).
INSERT INTO tenants (id, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'default')
ON CONFLICT (id) DO NOTHING;

-- Analyses: tenant isolation + LLM/verification payloads + retention.
ALTER TABLE analyses
    ADD COLUMN IF NOT EXISTS tenant_id UUID NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001' REFERENCES tenants(id);
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS llm_enrichment JSONB;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS verification_report JSONB;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS publication_verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_analyses_tenant ON analyses (tenant_id);

-- Response drafts: tenant-isolated, cascade-deleted with their analysis.
CREATE TABLE IF NOT EXISTS response_drafts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001' REFERENCES tenants(id),
    analysis_id         UUID REFERENCES analyses(id) ON DELETE CASCADE,
    strategy            TEXT,
    draft_content       JSONB,
    verification_report JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_drafts_tenant ON response_drafts (tenant_id);

-- Audit events: tenant-isolated; records LLM-call metadata (never raw prompt content in prod).
ALTER TABLE audit_events
    ADD COLUMN IF NOT EXISTS tenant_id UUID NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000001' REFERENCES tenants(id);
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS event_type TEXT;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS llm_model TEXT;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS token_count JSONB;
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events (tenant_id);

COMMENT ON TABLE chunks IS
    'PUBLIC data only (MPEP + published patents). Shared across tenants; never stores client work product.';
COMMENT ON TABLE analyses IS 'CLIENT work product — tenant-isolated, retention-limited.';
COMMENT ON TABLE response_drafts IS 'CLIENT work product — tenant-isolated, retention-limited.';
COMMENT ON TABLE audit_events IS 'CLIENT work product (privileged) — tenant-isolated.';
