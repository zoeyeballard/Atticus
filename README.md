# Atticus

**Verification-first AI assistant for USPTO office action responses.**

Atticus helps patent practitioners analyze office actions and draft responses for embedded
systems and computer architecture patents (USPTO Technology Centers 2100/2600). It is **not**
a general-purpose legal chatbot: every factual claim in any output must trace to a retrievable
source document, or it gets flagged.

> Working title. Summer prototype. Scope deliberately narrow: **office action analysis →
> response drafting → verification → human review.**

---

## Why this exists

General LLMs hallucinate patent numbers, MPEP sections, and case law with total confidence.
In patent prosecution that is malpractice. Atticus implements a closed-loop retrieval +
verification architecture so the model can only reference documents that were actually
retrieved from verified sources (USPTO, MPEP), and every assertion is checked before it
reaches the practitioner.

See [`docs/trusted-legal-ai-architecture.md`](docs/trusted-legal-ai-architecture.md) for the
full seven-layer trust architecture this project implements.

## Core design principles

1. **Verification-first** — every factual claim links to a retrievable source, or it is flagged.
2. **Structured over free-form** — analysis produces structured JSON, not essays.
3. **Closed-loop retrieval** — the LLM references only explicitly retrieved documents.
4. **Transparent uncertainty** — confidence scores are surfaced; guesses are never shown as facts.
5. **Human-in-the-loop** — Atticus drafts; the practitioner decides. Everything is editable.

## Architecture at a glance

```
USPTO / MPEP ──▶ data/ ──▶ retrieval/ ──▶ generation/ ──▶ verification/ ──▶ api/ ──▶ frontend/
   (sources)     (fetch &    (pgvector    (grounded,      (decompose +      (review UI,
                  parse)      search)      sourced)        entail-check)     audit trail)
```

| Layer          | Package              | Responsibility                                              |
| -------------- | -------------------- | ----------------------------------------------------------- |
| Data           | `src/data`           | Fetch & parse patents, office actions, MPEP                 |
| Models         | `src/models`         | Pydantic schemas for every structure                        |
| Retrieval      | `src/retrieval`      | Embeddings + pgvector search (closed-loop context)          |
| Generation     | `src/generation`     | Grounded analysis & response drafting (Claude)              |
| Verification   | `src/verification`   | Decompose → verify citations → entailment → confidence      |
| API            | `src/api`            | FastAPI endpoints + audit middleware                        |
| Frontend       | `frontend`           | React SPA for review                                        |

## Tech stack

Python 3.11 · FastAPI · PostgreSQL 16 + pgvector · pluggable LLM provider —
**Anthropic Claude** (`claude-sonnet-4-6` / `claude-haiku-4-5`) or **Google Gemini**
(`gemini-2.5-flash` / `-flash-lite`), selected by `LLM_PROVIDER` · sentence-transformers
(local embeddings, $0) · custom RAG pipeline (no LangChain) · React + Tailwind · Docker.

## Measured results

Test set: real USPTO office actions in TC 2100 (art units 2172/2183–2189), each a non-final
rejection with §103 present. **10 applications** total — 5 seen during development, 5 held out.

**Parse accuracy** (deterministic, `--no-llm`), against the registry ground truth extracted from
the OA text — 5 seen apps:

| Metric | Result |
|---|---|
| Rejection-type accuracy (from the authoritative document code) | 100% |
| Statutory-basis recall / precision | 100% / 100% |
| Claim-set accuracy | 100% |

**Draft-level hallucination eval** (`--mode draft`) — the pipeline that scores *generated* draft
citations (existence → location → entailment) is built and runs; see
[`docs/evaluation-methodology.md`](docs/evaluation-methodology.md) for the strict definitions of
*hallucination / review-needed / verified*. Headline numbers are pending a Gemini quota window (the
free tier's daily limit was exhausted during development) or a paid/Anthropic run.

**Honest caveats:**
- Small N (10 apps), single technology center (TC 2100).
- The registry ground truth shares regex lineage with the parser, so the 100% partly reflects
  self-consistency. **Independent human ground truth** (v2) tooling is in place
  (`scripts/annotate.py` + `scripts/score_against_ground_truth.py`, 10 blank templates in
  `data/ground_truth_v2/`); the annotation itself is pending. `rejection_type` ground truth **is**
  independent (from the document code).
- 5 of the 10 apps are **held out** (parser not run on them until after annotation).

## Quick start

```bash
# 1. Configure
cp .env.example .env          # then fill in ANTHROPIC_API_KEY and USPTO_API_KEY

# 2. Run the stack (Postgres + pgvector + API)
docker compose up --build

# API is now on http://localhost:8000  (docs at /docs)
# Frontend on http://localhost:3000
```

Single-image (Tier 2 — UI + API in one container against an external Postgres):

```bash
docker build -f Dockerfile.production -t atticus:latest .
docker run -p 8000:8000 --env-file .env atticus:latest   # → http://localhost:8000
```

Frontend dev server (React + Vite):

```bash
cd frontend && npm install && npm run dev   # → http://localhost:3000 (proxies /api to :8000)
```

Local development without Docker:

```bash
pip install -e ".[dev]"
python -m src.db.migrations          # apply schema (needs Postgres + pgvector running)
uvicorn src.main:app --reload
pytest
```

### CLI

```bash
# Analyze a stored office action file, deterministic parse only (no API keys needed):
python -m src.main analyze --file data/sample_office_actions/16-123456_non_final_103.txt --no-llm

# Analyze a live application (requires USPTO_API_KEY + an LLM key per LLM_PROVIDER):
python -m src.main analyze --application-number 19531961

# Validate services (free):
python scripts/validate_uspto.py 19531961     # USPTO ODP client
python scripts/validate_gemini.py             # Gemini key (or validate_anthropic.py)
```

### Evaluations & tests

```bash
# Backend + frontend tests
pytest -q                        # 46 backend tests
cd frontend && npm test          # 14 frontend (vitest) tests

# Evaluations (reports land in results/evaluations/)
python scripts/run_evaluation.py --mode no-llm                    # parse-only baseline
python scripts/run_evaluation.py --mode full                     # LLM analysis eval
python scripts/run_evaluation.py --mode draft --strategy argue   # draft-level hallucination eval
python scripts/compare_evaluations.py A.json B.json              # side-by-side provider/model

# Independent ground truth (human annotation)
python scripts/annotate.py --application 19531961                # blank template + OA path
python scripts/score_against_ground_truth.py --ground-truth data/ground_truth_v2/
```

## API endpoints

| Method | Path                                | Purpose                                   |
| ------ | ----------------------------------- | ----------------------------------------- |
| GET    | `/api/v1/health`                    | Liveness check                            |
| POST   | `/api/v1/analyze`                   | Analyze an office action → structured analysis + verification |
| POST   | `/api/v1/draft-response`            | Draft a response (argue / amend / both)   |
| POST   | `/api/v1/search-prior-art`          | Prior art vector search                   |
| POST   | `/api/v1/verify-claim`              | Verify a single claim or citation         |
| GET    | `/api/v1/audit-trail/{analysis_id}` | Full audit trail for an analysis          |

## Project status

Working prototype through Phase 4. Live USPTO ODP integration; PostgreSQL + pgvector with MPEP
(655 chunks) and patent text indexed; deterministic + LLM-enriched analysis; verification pipeline;
response drafting; React UI served from a single Docker image; a legal-compliance layer (data
classification, tenant isolation, a publication guard, and a routing guard that blocks client data
from training-enabled provider tiers); and an evaluation harness (parse-level and draft-level).
Consistent with the verification-first principle, LLM steps degrade to deterministic output rather
than emitting unverified content when a provider is unavailable.

## Known limitations

- USPTO only (no international patents); single technology center in the test set (TC 2100).
- Single-user prototype (schema supports multi-tenancy; no auth yet).
- Baseline embeddings (`all-MiniLM-L6-v2`); patent-tuned model planned.
- Draft-eval headline numbers pending a provider quota window; independent human ground truth
  (v2) pending annotation.
- **Compliance:** the Gemini free tier may train on inputs — used for public patent data only;
  real client work product requires a no-training tier (see
  [`docs/data-handling-policy.md`](docs/data-handling-policy.md)).

## License

Apache-2.0. See [LICENSE](LICENSE).
