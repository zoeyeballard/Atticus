# Atticus Data Handling Policy

This policy defines what data Atticus stores, where, and under what protections. It is enforced
in code by `src/config/data_classification.py`, the schema split in `src/db/migrations/`, and the
publication guard in `src/data/uspto_client.py`.

## Data Classification

### Public Data (freely storable)
- Published patents and patent applications (37 CFR 1.11)
- Office actions for published applications (37 CFR 1.14(a)(1)(iii))
- MPEP text (U.S. government work, no copyright)
- PTAB decisions
- Patent classification data

**Legal basis:** USPTO Open Data Portal content is explicitly designated as open data that
"can be freely used, reused and redistributed by anyone." In Atticus, all public data lives in
the shared `chunks` table and may be indexed, embedded, and cached permanently.

### Client Data (tenant-isolated, encrypted, retention-limited)
- Analysis results generated for a specific user/firm
- Response drafts
- User annotations and strategic decisions
- Audit trails of AI interactions

**Legal basis:** Attorney-client privilege requires confidentiality. Per *United States v.
Heppner* (S.D.N.Y., Feb. 17, 2026), AI-generated legal documents can lose privilege protection
when the AI platform's terms permit data retention, training, or third-party disclosure. Atticus
mitigates this by:
1. Using the **Anthropic Messages API** (not consumer claude.ai), which does not train on API
   inputs by default;
2. Isolating client data by `tenant_id` (enforced in `src/db/repositories.py` — no method returns
   another tenant's rows);
3. Never cross-pollinating client data into the shared retrieval corpus (`chunks` is public-only);
4. Supporting configurable retention (`tenants.retention_days`, `expires_at`) and **hard deletion**
   (`DELETE /api/v1/analyses/{id}` purges the analysis, its drafts, and its audit trail).

### Unpublished Applications (do not access)
- Unpublished pending applications are confidential under 35 U.S.C. 122(a) and 37 CFR 1.14(a).
- Atticus verifies publication status (`USPTOClient.is_published`) before fetching/indexing an
  application. Unpublished applications are refused unless the caller passes an explicit
  `--allow-unpublished` / `allow_unpublished` override (for authorized users).
- The ODP API only serves published data, so this is also enforced at the source.

## AI API Data Handling
- All LLM calls use the Anthropic Messages API (`src/generation/llm_client.py`), never consumer chat.
- Anthropic's API terms state that API inputs are not used for model training by default.
- **Production/enterprise:** obtain a Zero Data Retention (ZDR) agreement from Anthropic so inputs
  are not logged server-side.
- Client-specific content in prompts is classified as CLIENT data.
- System prompts and public context (MPEP, published patents) are PUBLIC data.
- The audit trail records LLM-call **metadata** (model, token counts, cost, purpose) — **not** raw
  prompt content in production, since prompts may contain privileged material.

## Encryption at Rest (requirement)
Client data (`analyses`, `response_drafts`, `audit_events`) must be encrypted at rest before any
real client data touches the system. For the prototype this is documented as a requirement;
implement (e.g. pgcrypto column encryption or volume-level encryption) before production.

## Professional Responsibility Alignment
- **ABA Model Rule 1.1 (Competence):** Atticus produces verification reports so practitioners can
  competently review AI outputs before relying on them.
- **ABA Model Rule 1.6 (Confidentiality):** Client data is tenant-isolated and never shared or
  used for training.
- **ABA Model Rules 5.1/5.3 (Supervision):** Atticus is a drafting assistant under attorney
  supervision, not an autonomous agent — every output is editable and reviewable to its source.

## Current implementation status (prototype)
| Control | Status |
|---|---|
| Public/client table separation | ✅ implemented (`chunks` vs `analyses`/`response_drafts`/`audit_events`) |
| Tenant isolation | ✅ enforced in the repository layer (single default tenant) |
| Publication guard | ✅ `is_published` + `--allow-unpublished` override |
| Hard deletion | ✅ `DELETE /api/v1/analyses/{id}` |
| Retention window | ◐ schema present (`retention_days`, `expires_at`); sweeper not yet scheduled |
| Audit = metadata only | ✅ metadata logged; raw prompt content not persisted |
| Encryption at rest | ☐ documented requirement; not implemented in prototype |
| Multi-tenant auth | ☐ single-user prototype; schema supports it |
| Anthropic ZDR | ☐ for production |
