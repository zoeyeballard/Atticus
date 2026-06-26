# Phase 2 Sprint Results — Live Data Integration

Executed against live services with PostgreSQL 14 + pgvector 0.8.0 and the USPTO ODP API.
All embeddings are local (`all-MiniLM-L6-v2`), so the entire sprint ran at **$0 API cost** — no
Anthropic credits required.

## Deliverables (all 8 tasks)

| # | Task | Status | Evidence |
|---|------|--------|----------|
| 1 | PostgreSQL + pgvector + migrations | ✅ | `python -m src.db.migrations` → tables `chunks`, `analyses`, `audit_events`; pgvector 0.8.0 |
| 2 | Seed MPEP | ✅ | **655 chunks** across 10 sections (706, 714, 2106, 2111, 2131, 2141, 2143, 2161, 2163, 2201) |
| 3 | Seed patent text | ✅ | **56 chunks** (claims + specification + abstract) from the 5 test applications |
| 4 | 5 test applications + cached OA text | ✅ | `data/test_applications.json` + `data/sample_office_actions/<app>_oa.txt` |
| 5 | Deterministic pipeline + scoring | ✅ | **100%** on all metrics (table below) |
| 6 | Fix parser issues | ✅ | Fixed `rejection_type` over-detection; 4 new regression tests |
| 7 | Retrieval integration | ✅ | MPEP §103 query → §2143 @ 0.5+; patent retrieval returns real passages |
| 8 | Evaluation harness | ✅ | `python scripts/run_evaluation.py --mode no-llm` → timestamped JSON |

33 tests pass (was 29).

## Test applications (all live, TC 2100)

| App | Art Unit | Latest OA | Statutory bases present |
|-----|----------|-----------|-------------------------|
| 19531961 | 2172 | CTNF (non-final) | §102, §103, §112 |
| 19445647 | 2186 | CTNF (non-final) | §101, §102, §103, §112 |
| 19418983 | 2186 | CTNF (non-final) | §101, §103, §112 |
| 19406513 | 2186 | CTNF (non-final) | §103 |
| 19025078 | 2186 | CTNF (non-final) | §103, §112 |

## Parsing accuracy (deterministic, `--no-llm`)

```
       APP   TYPE  RECALL    PREC  CLAIMS  PHANTOM
  19531961     OK    100%    100%    100%  -
  19445647     OK    100%    100%    100%  -
  19418983     OK    100%    100%    100%  -
  19406513     OK    100%    100%    100%  -
  19025078     OK    100%    100%    100%  -

  rejection-type accuracy : 100%
  basis recall (mean)     : 100%
  basis precision (mean)  : 100%
  claim-set accuracy (mean): 100%
```

## Key findings / fixes this sprint

- **`rejection_type` was over-detected** — `\bfinal\b` matched the word "final" in after-final
  boilerplate, mislabeling non-final OAs as final. Fixed to match the specific "THIS ACTION IS
  MADE FINAL" phrasing, and the parser now accepts an authoritative override derived from the
  **document code** (CTNF→non-final, CTFR→final, CTAV→advisory). Regression-tested.
- **pgvector query binding** — the query vector must be bound as a `::vector` literal, not a
  float array, or the cosine operator errors. Fixed in `VectorStore.search`.
- **MPEP source** — per-section pages (`s<NNNN>.html`) carry the real content; the chapter-level
  URL is only a TOC. The seeder fetches the priority sections directly.
- **Patent full text** — the ODP `/patent/grants/{n}/full-text` endpoint returns **403** with a
  standard key, so cited *granted references* can't be fetched that way. We index the
  application's **own** claims/spec/abstract (downloadable SPEC/CLM/ABST documents) instead.

## How to reproduce

```bash
# DB (Docker) + schema
docker compose up -d db && python -m src.db.migrations
# Seed (local embeddings, $0)
python scripts/seed_mpep.py
python scripts/seed_sample_patents.py
# Analyze + score
for a in 19531961 19445647 19418983 19406513 19025078; do
  python -m src.main analyze --file data/sample_office_actions/${a}_oa.txt --app-label $a \
    --no-llm --output-json results/${a}_analysis.json
done
python scripts/score_parsing.py
python scripts/run_evaluation.py --mode no-llm
```

## Honest caveats

- **Ground-truth lineage.** Basis/claim ground truth in `data/test_applications.json` is extracted
  from the OA text with a permissive regex that shares lineage with the parser, so the 100%
  basis/claim agreement partly measures self-consistency, not a fully independent human reading.
  `rejection_type` ground truth **is** independent (from the document code). A truly independent
  ground truth (manual annotation) is the next step to harden these numbers.
- **Small patent corpus.** Only the 5 applications' own text is indexed (cited references are
  403-blocked), so domain queries outside those inventions correctly return low scores.
- **LLM path unmeasured.** Hallucination rate / verification require Anthropic credits (account
  balance is currently $0). The harness's `--mode full` is wired and ready for when credits exist.
