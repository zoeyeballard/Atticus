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

### Part B — LLM integration ✅ (executed live via Google Gemini)
- **Provider abstraction:** `LLMClient` is now provider-agnostic (`LLM_PROVIDER=anthropic|gemini`)
  behind one interface — nothing downstream changed. Gemini uses `gemini-2.5-flash` (generation) and
  `gemini-2.5-flash-lite` (verification); thinking is disabled for deterministic structured output.
- **Task 4:** cost cap + prompt caching in `LLMClient`; `llm_audit_event()` is **metadata-only**
  (provider/model/tokens/cost/purpose — never prompt content).
- **Task 5 (ran):** `run_evaluation.py --mode full` over all 5 apps via Gemini →
  **100%** rejection-type/basis/claim accuracy, **0.0% hallucination rate** (target <5%).
- **Task 6 (ran):** verification pipeline (decompose → citation existence via USPTO search →
  entailment) executes on real content; 0 fabricated across the set.
- **Task 7 (ran):** response drafting produces grounded arguments with inline
  `[Source: US9,876,543B2, col. 4, lines 23-45]` citations (confidence 0.9). The drafter now feeds
  the LLM-extracted limitation mappings + cited passages so arguments are grounded; without that
  context the model correctly returns `INSUFFICIENT_CONTEXT` instead of fabricating.
- **Fix (important):** `patent_exists()` used the ODP grants full-text endpoint, which **403s**
  with a standard key — so it was marking every real cited patent as "fabricated". Rewrote it to
  use the ODP **search API** (`patentNumber` / `earliestPublicationNumber`); verified against real
  grants, publications, and fakes.
- CLI `verify` and `draft-response` subcommands added; `scripts/validate_gemini.py` confirms the key.
- **Note on the metric:** eval `--mode full` verifies the office action's own citations (all real →
  0% fabricated). The more probing hallucination test is on *generated drafts* — the drafter emits
  `[Source: …]` citations that the entailment/existence checks can score; wiring that into the eval
  loop is the next refinement.

### Part C — UI ✅ (builds clean; end-to-end verified offline)
- Full React app per the design system: dark sidebar + 5 views (New Analysis, Analysis Overview
  with collapsible rejection cards + claim-mapping table, slide-out Source Viewer, Response Draft
  editor with strategy selector + Export to Word, Settings). Professional palette + Merriweather/
  Inter/JetBrains Mono typography. Trust-signal verification badges (Verified/Review/Unverified/N.A.),
  no ML jargon. Wired to the real API (`frontend/src/api/client.js`) — no mock data.
- **Task 16 (API):** `src/api/routes/analyses.py` — list/get/delete analyses, create/get/save draft,
  source lookup, and `.docx` export for analysis + draft (`src/generation/docx_export.py`).
  Consistent `{error:{code,message,suggestion}}` envelope. **Tested** (offline integration tests).
- **Verified:** installed Node 20 + npm and ran `npm install && npm run build` — **builds clean**
  (47 modules, no errors). Copied the build to `./static` and served it via `Dockerfile.production`'s
  path (`main.py` static mount): one port serves the SPA, API, SPA fallback, and assets. Exercised
  the full UI data-flow against the running server offline — analyze (paste) → list → get →
  `.docx` export (valid OOXML, 37 KB) → source lookup → hard delete → 404. The draft editor uses
  styled textareas (not Tiptap) to keep deps minimal — a rich-text editor is a drop-in enhancement.

### Part D — Packaging ✅ (done + verified)
- **Task 18:** storage abstraction (`src/db/backends.py`: `VectorBackend`/`StorageBackend` +
  `PgVectorBackend`); `VectorStore` delegates to it. **Acceptance met:** no `psycopg` import outside
  `src/db/` (`grep` clean). `STORAGE_BACKEND` setting (postgres now; sqlite reserved).
- **Task 19:** `Dockerfile.production` (multi-stage: build frontend → serve from FastAPI) + SPA
  static serving in `main.py` (serves `./static` with `index.html` fallback when present).

## Tests
37 backend tests pass (added budget, rejection-type, and analyses-API integration tests).
Frontend has no automated tests yet (would need a jsdom/vitest setup).

## Blockers — all cleared
- The LLM path now runs on **Google Gemini** (free tier) instead of Anthropic, so Part B executes
  end-to-end. Anthropic remains available by setting `LLM_PROVIDER=anthropic` once credits exist.
- The earlier `npm` blocker is resolved (Node 20 + npm installed; frontend builds and serves).
- **Compliance caveat (built into the policy):** the Gemini **free tier may train on inputs**, so it
  is used only for **public** patent data. Real **client** work product must use a no-training tier
  (Anthropic API, paid Gemini, or Vertex AI) — see `docs/data-handling-policy.md`.

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
