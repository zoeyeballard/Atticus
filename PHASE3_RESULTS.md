# Phase 3 Results — LLM Integration, Legal Compliance, UI, Packaging

## Status by part

### Part A — Legal compliance ✅ (done + verified)
- **Task 1:** `002_compliance.sql` migrated live — `tenants` table, `tenant_id` on
  `analyses`/`response_drafts`/`audit_events`, `response_drafts` table, `expires_at`,
  `publication_verified`, tenant indexes, default tenant. Public data (`chunks`) is separated
  from client work product by table.
- **Task 2:** `src/config/data_classification.py` — `DataClass`, `STORAGE_POLICY`, `classify_data`,
  `DEFAULT_TENANT_ID`.
- **Task 3:** `USPTOClient.is_published()` + publication guard in `/analyze` and the CLI
  (`--allow-unpublished` override). Verified: our 5 apps report published.
- **Task 8:** `docs/data-handling-policy.md` (Heppner ruling, 37 CFR, ABA rules, control status).
- **Task 9:** `check_data_compliance()` in the eval harness; per-case issues in the report (clean).
- Repository is tenant-isolated (no method returns another tenant's rows) with **hard delete**.

### Part B — LLM integration ◐ (wired; execution blocked on credits)
- **Task 4:** cost cap + prompt caching already in `LLMClient`; added `llm_audit_event()` —
  **metadata-only** (model/tokens/cost/purpose, never prompt content).
- CLI `verify` and `draft-response` subcommands added.
- **Fix (important):** `patent_exists()` used the ODP grants full-text endpoint, which **403s**
  with a standard key — so it was marking every real cited patent as "fabricated". Rewrote it to
  use the ODP **search API** (`patentNumber` / `earliestPublicationNumber`); verified against real
  grants, real publications, and fakes.
- **Blocked:** Tasks 5–7 (LLM-enriched analysis, verification on LLM output, drafting) need
  Anthropic credits (account balance is $0 — calls return "credit balance too low"). Everything is
  wired; run `python scripts/run_evaluation.py --mode full` once credits exist.

### Part C — UI ◐ (built; needs `npm` build verification)
- Full React app per the design system: dark sidebar + 5 views (New Analysis, Analysis Overview
  with collapsible rejection cards + claim-mapping table, slide-out Source Viewer, Response Draft
  editor with strategy selector + Export to Word, Settings). Professional palette + Merriweather/
  Inter/JetBrains Mono typography. Trust-signal verification badges (Verified/Review/Unverified/N.A.),
  no ML jargon. Wired to the real API (`frontend/src/api/client.js`) — no mock data.
- **Task 16 (API):** `src/api/routes/analyses.py` — list/get/delete analyses, create/get/save draft,
  source lookup, and `.docx` export for analysis + draft (`src/generation/docx_export.py`).
  Consistent `{error:{code,message,suggestion}}` envelope. **Tested** (offline integration tests).
- **Caveat:** `npm` is unavailable in the build environment, so the React files were written and the
  import graph verified, but `npm install && npm run build` has **not** been run here. Run it locally
  to confirm the bundle builds. The draft editor uses styled textareas (not Tiptap) to keep deps
  minimal — swapping in a rich-text editor is a drop-in enhancement.

### Part D — Packaging ✅ (done + verified)
- **Task 18:** storage abstraction (`src/db/backends.py`: `VectorBackend`/`StorageBackend` +
  `PgVectorBackend`); `VectorStore` delegates to it. **Acceptance met:** no `psycopg` import outside
  `src/db/` (`grep` clean). `STORAGE_BACKEND` setting (postgres now; sqlite reserved).
- **Task 19:** `Dockerfile.production` (multi-stage: build frontend → serve from FastAPI) + SPA
  static serving in `main.py` (serves `./static` with `index.html` fallback when present).

## Tests
37 backend tests pass (added budget, rejection-type, and analyses-API integration tests).
Frontend has no automated tests yet (would need a jsdom/vitest setup).

## Two blockers (neither is a code defect)
1. **Anthropic credits** ($0 balance) → Part B execution (Tasks 5–7) and live draft generation.
2. **No `npm`** in this environment → Part C build verification.

## Reproduce
```bash
python -m src.db.migrations                       # applies 001 + 002
python -m src.main verify --text "..."            # verification (offline-degraded without credits)
docker build -f Dockerfile.production -t atticus:latest .   # one-image UI+API
cd frontend && npm install && npm run build        # verify the UI bundle (needs npm)
```

## What's next (post-Phase-3)
Add Anthropic credits → run `--mode full` for hallucination metrics; `npm run build` + browser QA
of the UI; then auth/real multi-tenancy, encryption at rest, and the Tier-3 Tauri desktop build
(roadmap R1–R8 in Phase3.md).
