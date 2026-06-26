# PHASE2_SPRINT.md — Prompt for Claude Code

## Context

Read these files first for full project context:
- `CLAUDE.md` — architecture, tech stack, data models, design principles
- `NEXT_STEPS.md` — current status, live validation results, what's been built
- `docs/trusted-legal-ai-architecture.md` — seven-layer trust architecture

## Current state

Phase 1 is complete. All seven layers are built. 29 tests pass. The USPTO client has been validated live against the ODP API (`api.uspto.gov`, `X-Api-Key` auth header). We successfully fetched and deterministically parsed a real office action from application 19531961 (Art Unit 2172) into structured rejection data: §102 claims 21–24/33–36, §103 claims 25–27/32, §112(b) claims 33–36.

Key things already discovered and fixed:
- Base URL needs `/api/v1` prefix; auth header is `X-Api-Key`
- Application metadata is under `patentFileWrapperDataBag[].applicationMetaData`
- Documents under `documentBag`; doc id is `documentIdentifier`; date is `officialDate`
- No inline OA text — office actions are downloadable artifacts only
- `get_office_action_text` downloads the document, preferring DOCX → XML → PDF
- USPTO OA PDFs are scanned images (no text layer) — DOCX is the reliable source
- Per-application `office-actions/{citations,rejections}` structured endpoints return 403 with a standard key — we rely on download-and-parse
- Parser handles real boilerplate: `Claim(s)`, literal `is/are`, headers with no `is/are` and no `§` symbol, comma-lists + ranges

Environment: Python 3.10 (pyproject.toml targets 3.11+ but everything compiles under 3.10 with `from __future__ import annotations`). API keys for both USPTO and Anthropic are in `.env`.

## This sprint's goal

Stand up PostgreSQL + pgvector, seed it with MPEP and patent data, and run the full deterministic (`--no-llm`) pipeline end-to-end against 5 real office actions. Measure parsing accuracy against manually created ground truth. All of this runs without Anthropic API credits — local embeddings only.

---

## Task 1: Stand up PostgreSQL + pgvector

Make sure `docker-compose.yml` has a working Postgres service with pgvector. If it exists already, verify it. If it needs fixes, fix it.

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: atticus-db
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-atticus}
      POSTGRES_USER: ${POSTGRES_USER:-atticus}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-atticus_dev}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U atticus"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

Then:
1. `docker-compose up -d db`
2. Verify pgvector: `docker exec -it atticus-db psql -U atticus -d atticus -c "CREATE EXTENSION IF NOT EXISTS vector;"`
3. Run database migrations: `python -m src.db.migrations` (or whatever migration command the project uses)
4. Verify tables exist and schema is correct

Add to `.env` if not already present:
```
POSTGRES_DB=atticus
POSTGRES_USER=atticus
POSTGRES_PASSWORD=atticus_dev
DATABASE_URL=postgresql://atticus:atticus_dev@localhost:5432/atticus
```

**Acceptance criteria:** Database is running, pgvector extension is enabled, all tables from the schema are created, and the app can connect.

---

## Task 2: Seed the MPEP into pgvector

Run or fix `scripts/seed_mpep.py` to download and index MPEP sections.

**What it should do:**

1. Download MPEP HTML from `https://www.uspto.gov/web/offices/pac/mpep/` for these priority chapters:
   - Chapter 700 (Examination of Applications) — focus on §706 (Rejection of Claims), §714 (Amendments)
   - Chapter 2100 (Patentability) — focus on §2106 (Patent Subject Matter Eligibility, Alice/Mayo), §2111 (Claim Interpretation), §2131–2135 (Anticipation under §102), §2141–2145 (Obviousness under §103, Graham v. John Deere), §2143 (KSR exemplary rationales), §2161–2163 (Written Description/Enablement under §112)
   - Chapter 2200 (Citation of Prior Art)

2. Parse HTML into clean text, preserving section/subsection structure

3. Chunk each subsection:
   - Target ~500 tokens per chunk
   - Never split mid-paragraph
   - Keep section header metadata with each chunk

4. Generate embeddings using `sentence-transformers` (`all-MiniLM-L6-v2`) — this is local, $0 cost

5. Store in pgvector with metadata:
   ```sql
   INSERT INTO mpep_chunks (
     chapter, section, subsection, revision_date,
     chunk_index, text, embedding
   ) VALUES (...)
   ```

**If MPEP download fails** (the USPTO website can be flaky), implement a fallback:
- Try downloading with retries and appropriate User-Agent header
- If download fails, check for any locally cached files in `data/mpep/`
- Log what was successfully downloaded vs. what failed

**Verification after seeding:**

```python
from src.retrieval.mpep_retriever import MPEPRetriever

retriever = MPEPRetriever()

# Test 1: KSR rationales (should return MPEP § 2143)
results = retriever.search("KSR rationales for combining prior art references")
assert any("2143" in r.section for r in results), "Should find MPEP § 2143"

# Test 2: Alice/Mayo (should return MPEP § 2106)
results = retriever.search("abstract idea patent eligibility 101")
assert any("2106" in r.section for r in results), "Should find MPEP § 2106"

# Test 3: Written description (should return MPEP § 2161-2163)
results = retriever.search("written description requirement enablement")
assert any("216" in r.section for r in results), "Should find MPEP § 2161+"

print(f"MPEP seeded: {retriever.count()} chunks indexed")
```

**Acceptance criteria:** At least 3 MPEP chapters indexed. Semantic search returns relevant sections for §101, §103, and §112 queries. All embeddings are local (no API calls).

---

## Task 3: Seed sample patents from test office actions

We already validated against application 19531961. Now:

1. Fetch the cited references from that office action (the patents the examiner relied on in the rejection)
2. For each cited patent:
   - Fetch full text via USPTO API
   - Parse claims into independent/dependent structure
   - Chunk specification by logical section (background, summary, detailed description, claims)
   - Generate local embeddings with sentence-transformers
   - Store in pgvector with metadata: `{patent_number, title, section_type, claim_number, chunk_index}`

3. Also fetch and index the application itself (19531961's published application text)

**Start small:** Just the cited references from app 19531961 first. Verify retrieval quality. Then we'll add more.

**Run:** `python scripts/seed_sample_patents.py`

If the script takes patent numbers as arguments:
```bash
# Replace with actual cited reference numbers from app 19531961's OA
python scripts/seed_sample_patents.py US10234567 US11345678
```

**Verification:**

```python
from src.retrieval.patent_retriever import PatentRetriever

retriever = PatentRetriever()

# Search for a concept from one of the cited patents
results = retriever.search("interrupt handling priority queue embedded processor")
for r in results:
    print(f"{r.patent_number} — {r.section_type}: {r.text[:150]}")

print(f"Patents seeded: {retriever.count()} chunks indexed")
```

**Acceptance criteria:** Cited patents from at least one test OA are indexed. Semantic search returns relevant patent passages for domain-specific queries.

---

## Task 4: Find and register 4 more test applications

We need 5 total test applications for the evaluation set. We already have 19531961. Find 4 more.

**Strategy:** Use the USPTO ODP Search API to find applications in the embedded systems / computer architecture space with non-final rejections:

```python
from src.data.uspto_client import USPTOClient

client = USPTOClient()

# Search for applications in target art units with pending status
# Art units 2182-2189 = computer architecture
# Art units 2611-2619 = communications
# Adjust the query based on what the ODP Search API actually accepts

# Option A: Search by art unit
results = client.search_applications(art_unit_range="2182-2189", status="pending")

# Option B: If the search API doesn't support that, search by CPC class
# G06F 15/78 = microcontrollers
# G06F 9/4401 = firmware
# G06F 13/24 = interrupt handling
results = client.search_applications(cpc_class="G06F15/78")
```

If the search API is limited, fall back to manually browsing Patent Center:
1. Go to https://patentcenter.uspto.gov
2. Use the search to find applications in art units 2182–2189
3. Look for ones with "CTNF" (Non-Final Rejection) in their transaction history
4. Prefer applications with §103 rejections (the primary use case)
5. Try to get variety: some with §103 only, some with mixed §103 + §101, some with §112 issues

**For each test application found, create a registry file:**

```json
// data/test_applications.json
[
  {
    "application_number": "19531961",
    "art_unit": "2172",
    "description": "Already validated — non-final with §102, §103, §112(b)",
    "rejection_types": ["102", "103", "112(b)"],
    "status": "validated"
  },
  {
    "application_number": "XXXXXXXX",
    "art_unit": "21XX",
    "description": "Brief description of the invention",
    "rejection_types": ["103"],
    "status": "found"
  }
  // ... 3 more
]
```

**Also**: for each application, fetch and cache the office action text locally so we don't hit the USPTO API repeatedly during testing:

```bash
python -c "
from src.data.uspto_client import USPTOClient
client = USPTOClient()
for app_num in ['19531961', 'XXXXXXXX', 'XXXXXXXX', 'XXXXXXXX', 'XXXXXXXX']:
    text = client.get_office_action_text(app_num)
    with open(f'data/sample_office_actions/{app_num}_oa.txt', 'w') as f:
        f.write(text)
    print(f'{app_num}: {len(text)} chars cached')
"
```

**Acceptance criteria:** 5 test applications identified. OA text cached locally. Application registry file created.

---

## Task 5: Run deterministic pipeline against all 5 test applications

This is the core validation step. Run the full `--no-llm` pipeline against each test application and evaluate parsing quality.

```bash
# For each test application:
python -m src.main analyze --application-number 19531961 --no-llm --output-json results/19531961_analysis.json
python -m src.main analyze --application-number XXXXXXXX --no-llm --output-json results/XXXXXXXX_analysis.json
# ... repeat for all 5
```

If the CLI doesn't support `--output-json`, add it or just capture stdout:
```bash
python -m src.main analyze --application-number 19531961 --no-llm > results/19531961_analysis.json 2>results/19531961_stderr.log
```

**For each result, check:**

1. **Rejection type correct?** (non-final vs. final)
2. **All rejection bases found?** (§101, §102, §103, §112 — compare against what you see in the actual OA)
3. **All cited references extracted?** (patent numbers match the OA)
4. **Claim numbers correct?** (claim ranges parsed properly: "Claims 1-4" → [1,2,3,4])
5. **No phantom rejections?** (rejections that appear in the parse but aren't in the actual OA)
6. **Claim grouping correct?** (claims grouped by rejection, not one-per-claim when they share the same basis and references)

**Create a simple scoring script:**

```python
# scripts/score_parsing.py
"""
Compare parsed results against expected values for each test application.
Print per-application and aggregate accuracy metrics.
"""
import json
import sys
from pathlib import Path

def score_application(result_path, expected):
    """Score a single application's parsing results."""
    with open(result_path) as f:
        result = json.load(f)
    
    scores = {
        "rejection_type_correct": False,
        "all_bases_found": False,
        "all_references_found": False,
        "claim_numbers_correct": False,
        "no_phantom_rejections": True,
    }
    
    # Check rejection type
    scores["rejection_type_correct"] = (
        result.get("rejection_type") == expected["rejection_type"]
    )
    
    # Check rejection bases
    found_bases = set()
    for rej in result.get("rejections", []):
        found_bases.add(rej.get("rejection_basis", ""))
    expected_bases = set(expected.get("rejection_types", []))
    scores["all_bases_found"] = expected_bases.issubset(found_bases)
    
    # ... add more checks as needed
    
    total = sum(scores.values())
    possible = len(scores)
    
    return scores, total, possible

def main():
    test_apps_path = Path("data/test_applications.json")
    results_dir = Path("results")
    
    with open(test_apps_path) as f:
        test_apps = json.load(f)
    
    total_score = 0
    total_possible = 0
    
    for app in test_apps:
        app_num = app["application_number"]
        result_path = results_dir / f"{app_num}_analysis.json"
        
        if not result_path.exists():
            print(f"  {app_num}: SKIPPED (no results file)")
            continue
        
        scores, score, possible = score_application(result_path, app)
        total_score += score
        total_possible += possible
        
        status = "✓" if score == possible else "✗"
        print(f"  {status} {app_num}: {score}/{possible}")
        for check, passed in scores.items():
            if not passed:
                print(f"      FAIL: {check}")
    
    print(f"\n  Aggregate: {total_score}/{total_possible} ({total_score/max(total_possible,1)*100:.0f}%)")

if __name__ == "__main__":
    main()
```

**Acceptance criteria:** All 5 applications parsed. Scoring script runs. Aggregate accuracy documented. Any parser failures identified and logged as issues to fix.

---

## Task 6: Fix parser issues found in Task 5

The first run against diverse real OAs will surface new formatting patterns the parser doesn't handle. Common ones to expect:

- **Different heading styles:** Some examiners use "Claim Rejections - 35 USC § 103" while others use "The following is a quotation of 35 U.S.C. 103..."
- **Inline vs. block citation format:** "Smith (US 10,234,567)" vs. "U.S. Patent No. 10,234,567 to Smith et al."
- **Non-standard claim ranges:** "Claims 1, 3-5, and 7" or "Claim 1 (and claim 8 by dependency)"
- **Mixed art rejections:** §103 using one primary reference with different secondary references for different claim subsets
- **Double patenting rejections:** Different structure from statutory rejections
- **Means-plus-function interpretations under §112(f):** Sometimes embedded in §112 rejections

**For each issue:**
1. Add the failing OA text as a test case in `tests/unit/test_rejection_extraction.py`
2. Fix the parser
3. Verify all existing tests still pass
4. Re-run against all 5 applications
5. Update scoring

**Acceptance criteria:** All previously passing tests still pass. New test cases added for each new formatting pattern discovered. Aggregate scoring improves or stays stable.

---

## Task 7: Validate retrieval integration

Now that we have MPEP and patents seeded, test the retrieval pipeline against real rejection scenarios:

```python
from src.retrieval.patent_retriever import PatentRetriever
from src.retrieval.mpep_retriever import MPEPRetriever

patent_retriever = PatentRetriever()
mpep_retriever = MPEPRetriever()

# Scenario: §103 rejection in the embedded systems space
# Given a claim limitation from one of our test OAs,
# can we retrieve the relevant prior art passage?

limitation = "a processor configured to handle interrupt requests using a priority queue"

# Should return passages from the cited references
patent_results = patent_retriever.search(limitation, top_k=5)
print("Patent retrieval results:")
for r in patent_results:
    print(f"  {r.patent_number} (score: {r.score:.3f}): {r.text[:150]}")

# Should return MPEP guidance on §103 analysis
mpep_query = "obviousness analysis combining references motivation to combine"
mpep_results = mpep_retriever.search(mpep_query, top_k=5)
print("\nMPEP retrieval results:")
for r in mpep_results:
    print(f"  MPEP §{r.section} (score: {r.score:.3f}): {r.text[:150]}")
```

**What to look for:**
- Are the top results actually relevant? (precision)
- Are the cited patents from the OA appearing in the results? (recall)
- Are the MPEP sections topically appropriate?
- Are there irrelevant results cluttering the top-k? (noise)

**If retrieval quality is poor:**
- Check chunking strategy — chunks may be too large or too small
- Check if embeddings are being generated correctly
- Consider adjusting the similarity threshold
- Try different query formulations

**Acceptance criteria:** Patent retrieval returns relevant cited art passages for test claim limitations. MPEP retrieval returns topically appropriate sections. Retrieval quality is documented.

---

## Task 8: Create evaluation harness

Build the foundation for systematic hallucination measurement (even though we can't run the LLM path yet, the harness should be ready):

```python
# scripts/run_evaluation.py
"""
Run the full Atticus pipeline against all test applications
and produce an evaluation report.

Supports two modes:
  --no-llm    : deterministic parsing only (free)
  --full      : parsing + LLM enrichment + verification (needs API credits)
"""
import argparse
import json
from pathlib import Path
from datetime import datetime

def run_evaluation(mode="no-llm"):
    test_apps_path = Path("data/test_applications.json")
    results_dir = Path("results/evaluations")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    with open(test_apps_path) as f:
        test_apps = json.load(f)
    
    evaluation = {
        "timestamp": timestamp,
        "mode": mode,
        "applications": [],
        "aggregate": {}
    }
    
    for app in test_apps:
        app_num = app["application_number"]
        # Run pipeline
        # Compare against ground truth
        # Record metrics
        # ...
        pass
    
    # Calculate aggregate metrics
    # ...
    
    output_path = results_dir / f"eval_{mode}_{timestamp}.json"
    with open(output_path, "w") as f:
        json.dump(evaluation, f, indent=2)
    
    print(f"Evaluation saved to {output_path}")
    return evaluation

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["no-llm", "full"], default="no-llm")
    args = parser.parse_args()
    run_evaluation(args.mode)
```

**Metrics to track:**
- Rejection type accuracy (% correct)
- Rejection basis recall (% of statutory bases found)
- Rejection basis precision (% of found bases that are correct)
- Reference extraction recall (% of cited patents found)
- Reference extraction precision (% of found patents that are real)
- Claim number accuracy (% of claim sets parsed correctly)
- Overall parse accuracy (composite score)
- When LLM mode is available: hallucination rate (fabricated claims / total claims)
- When LLM mode is available: verification pass rate (% of claims that verify)

**Acceptance criteria:** Evaluation harness runs in `--no-llm` mode against all test applications. Results are saved as timestamped JSON. Baseline metrics are recorded.

---

## End-of-sprint deliverables

When this sprint is complete, we should have:

1. ✅ PostgreSQL + pgvector running and populated
2. ✅ MPEP indexed (chapters 700, 2100, 2200) with working semantic search
3. ✅ Cited patents indexed from test OAs with working semantic search
4. ✅ 5 test applications identified with cached OA text
5. ✅ Deterministic pipeline tested against all 5 applications
6. ✅ Parser issues found and fixed, with new test cases
7. ✅ Retrieval quality validated
8. ✅ Evaluation harness built and baseline metrics recorded
9. ✅ All tests passing (existing 29 + new ones added during this sprint)

**What comes next after this sprint:**
- Add Anthropic API credits ($5–10)
- Run full LLM-enriched pipeline
- Measure hallucination rate with verification layers active
- Create ground-truth response drafts for evaluation
- Test the frontend UI against real data
- Begin response drafting evaluation