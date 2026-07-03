# PHASE4_SPRINT.md — Hardening: Measure What Matters

## Context files to read first
- `CLAUDE.md` — architecture, tech stack, design principles
- `PHASE3_SPRINT.md` + Phase 3 results — what exists now
- `docs/trusted-legal-ai-architecture.md` — seven-layer trust model
- `docs/data-handling-policy.md` — data classification and provider rules

## Current state (post-Phase 3)

All four Phase 3 parts complete. 37 backend tests passing. Single Docker image serves
UI + API. LLM path runs on Gemini free tier (public data only); provider abstraction
supports Anthropic when credits exist. Eval shows 100% parse accuracy and 0.0%
hallucination — but that metric only verifies the OA's own citations (which are
always real). The generated-draft citations — where hallucination actually happens —
are not yet scored.

## This sprint's mission

Harden the claims we can make about Atticus. By the end of this sprint we should be
able to say, with methodology to back it:

> "On N independently annotated office actions, Atticus generated response drafts
> containing M sourced assertions. X% verified against their cited sources, Y% were
> flagged for review, Z% were fabricated or misattributed — and every flagged
> assertion was surfaced to the user before the draft was shown."

That sentence is the product. Everything in this sprint serves it.

---

## Task 1: Draft-level hallucination evaluation (the headline task)

Extend the evaluation pipeline to score *generated drafts*, not just parsed OAs.

**The pipeline to build:**

```
For each test application:
  1. Run full analysis (existing)
  2. Generate response draft with strategy=argue (existing)
  3. NEW: Decompose the draft into atomic assertions (claim_decomposer on draft text)
  4. NEW: For each assertion, classify:
       - SOURCED: has an inline [Source: ...] citation
       - LEGAL: statement of law / MPEP procedure
       - ARGUMENT: attorney-style reasoning (not independently verifiable)
       - FACTUAL: factual claim without a citation ← these are the danger zone
  5. NEW: For each SOURCED assertion:
       a. Existence check: does the cited document exist? (USPTO search API)
       b. Location check: does the cited location exist in that document?
          (col/line for grants, paragraph for publications — fetch the document
          text we have indexed; if not indexed, fetch and cache it)
       c. Entailment check: does the cited passage support the assertion?
          (verification model, ENTAILS / CONTRADICTS / NEUTRAL)
  6. NEW: For each FACTUAL assertion without a citation: flag as UNSOURCED
     (per our grounding rules, factual claims must carry sources — an unsourced
      factual claim is a grounding-rule violation even if it happens to be true)
  7. Record per-draft and aggregate metrics
```

**Metrics to report (this is the schema for `results/evaluations/draft_eval_*.json`):**

```json
{
  "timestamp": "...",
  "provider": "gemini|anthropic",
  "generation_model": "...",
  "verification_model": "...",
  "applications": [
    {
      "application_number": "19531961",
      "draft_assertions_total": 42,
      "sourced": 28,
      "legal": 6,
      "argument": 5,
      "factual_unsourced": 3,
      "sourced_breakdown": {
        "verified": 25,
        "location_invalid": 1,
        "entailment_neutral": 1,
        "entailment_contradicts": 0,
        "fabricated_document": 1
      }
    }
  ],
  "aggregate": {
    "hallucination_rate": "fabricated + contradicts / sourced",
    "review_rate": "neutral + location_invalid + factual_unsourced / total",
    "verified_rate": "verified / sourced"
  }
}
```

**Definitions (be strict and document them in `docs/evaluation-methodology.md`):**
- **Hallucination** = fabricated document OR entailment CONTRADICTS. These are the
  malpractice-grade failures.
- **Review-needed** = location invalid, entailment NEUTRAL, or unsourced factual claim.
  Not proven wrong, but a practitioner must check before filing.
- **Verified** = document exists, location exists, passage entails the assertion.

**Command to add:**
```bash
python scripts/run_evaluation.py --mode draft --strategy argue
```

**Acceptance criteria:** Draft eval runs over all test applications. JSON report
generated with the schema above. `docs/evaluation-methodology.md` updated with the
strict definitions. The aggregate numbers print at the end of the run in a readable
table.

---

## Task 2: Classification-aware LLM routing guard

Turn the data-handling policy caveat into an enforced invariant.

**Implementation:**

```python
# src/generation/llm_client.py

# Provider capability registry — extend as providers/tiers are added
PROVIDER_CAPABILITIES = {
    ("gemini", "free"):      {"trains_on_inputs": True},
    ("gemini", "paid"):      {"trains_on_inputs": False},
    ("anthropic", "api"):    {"trains_on_inputs": False},
    ("vertex", "enterprise"):{"trains_on_inputs": False},
}

class DataClassificationError(Exception):
    """Raised when client data would be routed to a training-enabled provider."""

class LLMClient:
    def call(self, messages, *, data_class: DataClass, purpose: str, ...):
        caps = PROVIDER_CAPABILITIES[(self.provider, self.tier)]
        if data_class in (DataClass.CLIENT, DataClass.PRIVILEGED) and caps["trains_on_inputs"]:
            raise DataClassificationError(
                f"Cannot send {data_class.value} data to {self.provider}/{self.tier}: "
                "this provider tier may train on inputs, which risks destroying "
                "attorney-client privilege (see docs/data-handling-policy.md and "
                "U.S. v. Heppner). Configure a no-training provider: "
                "LLM_PROVIDER=anthropic, or LLM_PROVIDER=gemini with LLM_TIER=paid."
            )
        ...
```

**Every call site must now pass `data_class`.** The classification comes from the
pipeline context: analyses of user-supplied OA text are CLIENT; MPEP/eval-harness
work on our public test apps can be marked PUBLIC explicitly.

**Add `LLM_TIER` to settings** (`free|paid|api|enterprise`), defaulting conservatively:
if unset, assume the *most restrictive* interpretation (Gemini → `free` → blocks
client data).

**UI surfacing:** if the guard trips during an interactive analysis, the API returns
the standard error envelope with code `PROVIDER_NOT_PERMITTED_FOR_CLIENT_DATA` and a
plain-language message. The frontend shows it as a clear, non-scary explanation with
a link to Settings.

**Tests:** unit tests that (a) CLIENT + gemini/free raises, (b) PUBLIC + gemini/free
passes, (c) CLIENT + anthropic/api passes, (d) unset tier defaults to blocking.

**Acceptance criteria:** It is structurally impossible for CLIENT-classified content
to reach a training-enabled provider tier. Tests prove it.

---

## Task 3: Independent ground truth (human annotation)

**This task is for the human (Zoey), not Claude Code.** Claude Code builds the
scaffolding; the annotation itself must be done cold, without looking at parser output.

**Claude Code builds:**

1. An annotation template + helper script:
   ```bash
   python scripts/annotate.py --application 19531961
   # → opens/creates data/ground_truth_v2/19531961.yaml with a blank template
   #   and prints the path to the cached OA text for reading
   ```
   Template fields: rejection_type, per-rejection {basis, claim_numbers, references
   (primary/secondary), notes}, objections, annotator, date, minutes_spent.

2. A diff scorer:
   ```bash
   python scripts/score_against_ground_truth.py --ground-truth data/ground_truth_v2/
   # → per-app and aggregate precision/recall vs. BOTH the deterministic parse
   #   and the LLM-enriched analysis, using ONLY the v2 human annotations
   ```

3. Fetch + cache OAs for **5 NEW applications** (same art-unit strategy as Phase 2,
   TC 2100/2600, CTNF with §103 present) into `data/sample_office_actions/`, and add
   them to `data/test_applications.json` with `"ground_truth": "pending"`. Do NOT
   run the parser on them yet — they are the held-out set.

**The human does (est. 2–4 hours total):**
- For each of the 10 apps (5 original + 5 new): read the cached OA text top to
  bottom, fill in the YAML annotation from your own reading only.
- For the 5 new apps ONLY after annotating: run the pipeline and score.

**Acceptance criteria:** 10 human-annotated ground truth files exist. Scorer reports
parser and LLM accuracy against human annotations, separately for the original 5
(seen during development) and the new 5 (held out). Both numbers go in the README.

---

## Task 4: Frontend tests + browser QA checklist

**Claude Code:**
1. Set up vitest + @testing-library/react + jsdom in `frontend/`.
2. Write tests for the highest-risk components:
   - `VerificationBadge` — renders correct state/tooltip for all 4 statuses
   - `RejectionCard` — collapse/expand, renders claims/references from fixture data
   - `ClaimMappingTable` — renders rows, [View ↗] fires the source-viewer callback
   - `api/client.js` — error envelope parsing (mock fetch)
3. Add `npm test` to CI (or a `make test` target that runs backend + frontend tests).

**Human browser QA checklist (add as `docs/qa-checklist.md`):**
```
[ ] New Analysis: analyze by app number (19531961) — progress states appear
[ ] New Analysis: paste OA text — analysis completes
[ ] New Analysis: invalid app number — friendly error, no crash
[ ] Overview: all rejection cards render; badges show; expand/collapse works
[ ] Claim table: [View ↗] opens Source Viewer with highlighted passage
[ ] Source Viewer: Esc / outside-click / × all close it
[ ] Draft: generate with strategy=argue; inline [Source: ...] citations visible
[ ] Draft: edit text, Save Draft, reload page — edits persisted
[ ] Draft: Export to Word — .docx opens in Word/Pages with correct formatting
[ ] Analysis: Export Analysis .docx — opens correctly
[ ] Sidebar: recent analyses list updates after new analysis
[ ] Delete: delete an analysis — disappears from list; direct URL → 404 page
[ ] Settings: retention + budget fields render (even if static for now)
[ ] Guard: with LLM_TIER=free, analyzing as CLIENT shows the provider-not-permitted
    message (temporarily force data_class=CLIENT to test)
```

**Acceptance criteria:** vitest suite runs green. QA checklist committed. Human
completes the checklist against the Docker image and files issues for anything broken.

---

## Task 5: Provider comparison (conditional — needs Anthropic credits)

If/when Anthropic credits exist:

```bash
LLM_PROVIDER=anthropic python scripts/run_evaluation.py --mode draft --strategy argue
LLM_PROVIDER=gemini    python scripts/run_evaluation.py --mode draft --strategy argue
python scripts/compare_evaluations.py results/evaluations/draft_eval_anthropic_*.json \
                                       results/evaluations/draft_eval_gemini_*.json
```

`compare_evaluations.py` prints a side-by-side table: verified rate, review rate,
hallucination rate, mean cost per draft, mean latency. This comparison — measured on
independently annotated legal documents — is write-up material.

**Acceptance criteria:** comparison script exists and runs on any two eval JSONs
(testable now with two Gemini runs at different models).

---

## Task 6: README + results write-up

Update `README.md` with:
1. What Atticus is (3 sentences, no jargon)
2. The architecture diagram (text is fine)
3. **The measured results table** — parse accuracy vs. human ground truth (seen +
   held-out), draft verified/review/hallucination rates, with links to
   `docs/evaluation-methodology.md` for definitions
4. Honest limitations (small N, single tech center, ground-truth caveats resolved
   or noted)
5. The full run-it-yourself guide (below — keep it in sync)

---

## RUNBOOK — How to run and test everything yourself

This section is for the human. Copy-paste friendly. Assumes repo root.

### One-time setup

```bash
# 1. Environment file (first time only)
cp .env.example .env
# Edit .env and set at minimum:
#   USPTO_API_KEY=...            (from data.uspto.gov/myodp)
#   LLM_PROVIDER=gemini          (or anthropic)
#   GEMINI_API_KEY=...           (or ANTHROPIC_API_KEY=...)
#   LLM_TIER=free                (be honest — the guard depends on it)
#   POSTGRES_DB=atticus POSTGRES_USER=atticus POSTGRES_PASSWORD=atticus_dev
#   DATABASE_URL=postgresql://atticus:atticus_dev@localhost:5432/atticus

# 2. Python deps (3.11+ recommended)
pip install -e ".[dev]"          # or: pip install -e . --break-system-packages

# 3. Database up + schema
docker compose up -d db
python -m src.db.migrations      # applies 001 + 002

# 4. Seed public data (local embeddings, $0)
python scripts/seed_mpep.py
python scripts/seed_sample_patents.py
```

### Option A — Run the full app in one container (closest to "the product")

```bash
docker build -f Dockerfile.production -t atticus:latest .
docker run --rm -p 8000:8000 --env-file .env \
  --add-host=host.docker.internal:host-gateway \
  atticus:latest
# If DATABASE_URL points at localhost, change it for the container:
#   DATABASE_URL=postgresql://atticus:atticus_dev@host.docker.internal:5432/atticus

# → open http://localhost:8000
```

### Option B — Run backend + frontend separately (dev mode, hot reload)

```bash
# Terminal 1 — backend
uvicorn src.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
# → open http://localhost:3000  (frontend proxies/points to :8000)
```

### Smoke-test the API directly

```bash
curl http://localhost:8000/api/v1/health

# Analyze a known-good test application
curl -s -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"application_number": "19531961"}' | python -m json.tool

# List analyses / export docx
curl -s "http://localhost:8000/api/v1/analyses" | python -m json.tool
curl -s -o analysis.docx "http://localhost:8000/api/v1/analyses/<ID>/export"
```

### CLI equivalents (no server needed)

```bash
# Deterministic only (free, offline-safe)
python -m src.main analyze --file data/sample_office_actions/19531961_oa.txt \
  --app-label 19531961 --no-llm --output-json results/19531961.json

# Full analysis with LLM
python -m src.main analyze --application-number 19531961 \
  --output-json results/19531961_full.json

# Verify + draft
python -m src.main verify --analysis-id <ID>
python -m src.main draft-response --analysis-id <ID> --strategy argue
```

### Run all tests

```bash
pytest -q                        # backend (should be 37+ green)
cd frontend && npm test          # frontend (after Task 4)
```

### Run the evaluations

```bash
python scripts/run_evaluation.py --mode no-llm      # parse-only baseline
python scripts/run_evaluation.py --mode full        # LLM analysis eval
python scripts/run_evaluation.py --mode draft --strategy argue   # NEW: draft-level
python scripts/score_against_ground_truth.py --ground-truth data/ground_truth_v2/
```

### In the browser — the 5-minute demo path

1. `http://localhost:8000` → New Analysis
2. Enter `19531961` → Analyze → watch progress states
3. Overview: expand the §103 card → claim mapping table
4. Click [View ↗] on any row → Source Viewer with highlighted passage
5. [Draft Response] → strategy Argue → read the draft, note inline [Source: ...] tags
6. Export to Word → open the .docx
7. Sidebar → confirm the analysis appears under Recent

---

## End-of-sprint deliverables

1. ✅ Draft-level hallucination eval (`--mode draft`) with strict, documented definitions
2. ✅ Classification-aware LLM routing guard, tested (CLIENT data cannot reach training tiers)
3. ✅ Annotation tooling + 10 human ground-truth files (5 seen, 5 held out) + scorer
4. ✅ Frontend vitest suite green; browser QA checklist completed by human
5. ✅ Provider comparison script (run when Anthropic credits exist)
6. ✅ README with measured results and the runbook
7. ✅ All backend tests passing (37+), no regressions

## Budget estimate

| Item | Cost |
|---|---|
| Draft eval on 10 apps (Gemini free / public data) | $0 |
| Same on Anthropic (if credits added) | ~$5–12 |
| Everything else | $0 |

## What comes after Phase 4

- Auth + real multi-tenancy; encryption at rest
- Tauri desktop build (roadmap R1–R8)
- Expand corpus + test set beyond TC 2100/2600
- The write-up: methodology + results (law school apps / blog / potential users)