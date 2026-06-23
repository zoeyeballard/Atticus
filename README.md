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

Python 3.11 · FastAPI · PostgreSQL 16 + pgvector · Anthropic Claude
(`claude-sonnet-4-6` generation, `claude-haiku-4-5` verification) · sentence-transformers ·
custom RAG pipeline (no LangChain — full control over retrieve/generate/verify) · React + Tailwind ·
Docker.

## Quick start

```bash
# 1. Configure
cp .env.example .env          # then fill in ANTHROPIC_API_KEY and USPTO_API_KEY

# 2. Run the stack (Postgres + pgvector + API)
docker compose up --build

# API is now on http://localhost:8000  (docs at /docs)
# Frontend on http://localhost:3000
```

Local development without Docker:

```bash
pip install -e ".[dev]"
uvicorn src.main:app --reload
pytest
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

This repository is an actively-scaffolded prototype. Phase 1 (data models, config, API
surface, grounded-generation prompt scaffolding) is in place; retrieval, generation, and
verification implementations are being filled in per the build plan in
[`CLAUDE.md`](CLAUDE.md). Modules not yet implemented raise `NotImplementedError` rather than
returning unverified output — consistent with the verification-first principle.

## Known limitations

- USPTO only (no international patents).
- Single-user prototype (no auth / multi-tenancy).
- Baseline embeddings (`all-MiniLM-L6-v2`); patent-tuned model planned.

## License

Apache-2.0. See [LICENSE](LICENSE).
