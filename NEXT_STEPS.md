# NEXT_STEPS.md — Atticus Phase 2: Live Data Integration

## Status: Phase 1 complete. All seven layers built. 18 offline tests passing.

## This week's mission

Wire up live services, seed real patent data, and run the full pipeline against an actual USPTO office action. By the end of this sprint, Atticus should be able to: take a real application number → fetch the office action from the USPTO API → parse it into structured rejection data → retrieve relevant prior art and MPEP sections → generate a grounded analysis → verify every claim → present results with confidence scores.

---

## Step 0: USPTO API access (do this first — it's a blocker)

The USPTO Open Data Portal underwent a major transition. The legacy Developer Hub was decommissioned on June 5, 2026. All APIs are now through the new ODP at `data.uspto.gov` and `api.uspto.gov`.

**Action items:**

1. Go to https://data.uspto.gov and sign in with a USPTO.gov account
   - If you don't have one: create at https://account.uspto.gov
   - You must verify with ID.me (one-time identity verification)
   - This is required for API key issuance — no workaround

2. Once verified, go to https://data.uspto.gov/myodp to get your API key

3. Add the key to your `.env`:
   ```
   USPTO_API_KEY=your-key-here
   ```

4. Note the rate limits: the USPTO throttles heavy users and returns HTTP 429 if you exceed weekly quotas. The existing on-disk cache in the data layer should help — but be mindful during seeding.

**API base URL:** `https://api.uspto.gov/api/v1/`

**Key endpoints you'll hit:**

| Endpoint | Purpose |
|----------|---------|
| `GET /patent/applications/{appNum}/documents` | List all documents (OAs, responses, etc.) for an application |
| `GET /patent/applications/{appNum}` | Application metadata (filing date, status, art unit, examiner) |
| ODP Office Action Text Retrieval API | Full text of office actions |
| ODP Office Action Citations API | Structured citation data from OAs |
| ODP Office Action Rejections API | Structured rejection data from OAs |
| ODP Enriched Citations API | Enhanced citation context |
| `GET /datasets/products/{productId}` | Bulk data product access |

The OA-specific APIs (text retrieval, citations, rejections, enriched citations) were recently migrated from the legacy Developer Hub to ODP. Check the Swagger docs at `data.uspto.gov` for current schemas — they may have changed in the migration.

**Useful reference:** There's a community Go client at `github.com/patent-dev/uspto-odp` that wraps all 53 ODP endpoints. Even though Atticus is Python, the Go client's source is useful documentation for the API's quirks, edge cases, and normalization logic (e.g., application number format handling, PCT number standardization).

---

## Step 1: Validate the USPTO client against live data

Before seeding anything, confirm the existing `src/data/uspto_client.py` works against the live API.

**Test sequence:**

```bash
# Set your API key
export USPTO_API_KEY=your-key

# Test 1: Fetch application metadata for a known embedded systems patent
# Application 16/123,456 is a placeholder — use real numbers below
python -c "
from src.data.uspto_client import USPTOClient
client = USPTOClient()
result = client.get_application('16835899')
print(result)
"

# Test 2: Fetch documents list for that application
python -c "
from src.data.uspto_client import USPTOClient
client = USPTOClient()
docs = client.get_documents('16835899')
for d in docs:
    print(d['documentCode'], d.get('documentDescription', ''))
"

# Test 3: Fetch office action text
python -c "
from src.data.uspto_client import USPTOClient
client = USPTOClient()
oa_text = client.get_office_action_text('16835899')
print(oa_text[:2000])
"
```

**If the API client needs updates** for the new ODP endpoint structure, fix them now. The migration changed some paths and response schemas. Common issues:
- Endpoint paths may have changed from the legacy Developer Hub format
- Response JSON structure may differ (the ODP uses a consistent wrapper format)
- Authentication header format: `X-Api-Key: {your_key}` or `api_key` query parameter
- Date formats and null handling may differ

**Fix any issues before proceeding.** The data pipeline is the foundation.

---

## Step 2: Seed test applications

Here are specific real applications in TC 2100/2600 (computer architecture, communications, embedded systems) that you can use for testing. These are chosen because they have substantive office actions with § 103 rejections — the core use case.

### Starter test applications

Use these to validate the full pipeline. Search for them on USPTO Patent Center (https://patentcenter.uspto.gov) to manually verify your tool's output.

**Category: Embedded systems / microcontroller / firmware**
- Search Patent Center for recently published applications in CPC class G06F 15/78 (microcontrollers) or G06F 9/4401 (firmware) with non-final rejections
- Art units 2182–2189 (computer architecture) and 2611–2619 (communications) are your sweet spot

**Category: RTOS / interrupt handling / scheduling**
- CPC class G06F 9/4812 (task scheduling) and G06F 13/24 (interrupt handling)
- These map directly to your embedded systems expertise

**How to find good test cases efficiently:**

```
# Use the ODP Search API to find applications in your target art units
# with office actions containing § 103 rejections
GET https://api.uspto.gov/api/v1/patent/applications?query=artUnit:2182 AND status:pending
```

Or use Patent Center's public search:
1. Go to https://patentcenter.uspto.gov
2. Search for applications in art unit 2182–2189
3. Filter to those with "Non-Final Rejection" in their transaction history
4. Pick 5–10 with § 103 rejections (visible in the office action)
5. Record the application numbers

**Manual ground-truth creation:**
For each test application, manually create a ground-truth JSON file:
```
data/evaluation_ground_truth/
├── app_16XXXXXX_ground_truth.json
├── app_17XXXXXX_ground_truth.json
└── ...
```

Each ground-truth file should contain:
```json
{
  "application_number": "16XXXXXX",
  "rejection_type": "non-final",
  "rejections": [
    {
      "claim_numbers": [1, 4, 7],
      "basis": "103",
      "primary_reference": "US10,XXX,XXX",
      "secondary_references": ["US11,XXX,XXX"],
      "key_limitation_mappings": {
        "claim_1_limitation_a": "Primary ref, col. X, lines Y-Z"
      }
    }
  ],
  "notes": "Your manual analysis notes"
}
```

This is the gold standard you'll measure against. Start with 5 applications. You'll expand to 20+ during the evaluation phase.

---

## Step 3: Start PostgreSQL + pgvector

```bash
# Start the database
docker-compose up -d db

# Verify pgvector is available
docker exec -it atticus-db psql -U atticus -d atticus -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations
python -m src.db.migrations  # or alembic upgrade head, depending on your setup
```

**If docker-compose isn't set up yet or needs adjustments:**

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: atticus-db
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: atticus
      POSTGRES_USER: atticus
      POSTGRES_PASSWORD: atticus_dev
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

Update `.env`:
```
DATABASE_URL=postgresql://atticus:atticus_dev@localhost:5432/atticus
```

---

## Step 4: Seed the MPEP

```bash
python scripts/seed_mpep.py
```

**What this should do:**
1. Download MPEP chapters 700, 2100, 2200 from USPTO (HTML format from https://www.uspto.gov/web/offices/pac/mpep/)
2. Parse into sections and subsections
3. Chunk each subsection (target ~500 tokens per chunk, don't split mid-paragraph)
4. Generate embeddings for each chunk
5. Store in pgvector with metadata: `{mpep_chapter, mpep_section, mpep_subsection, revision_date, chunk_index}`

**If the script needs to be written or updated, key sections to prioritize:**
- MPEP § 2141–2145 (Graham v. John Deere analysis for § 103)
- MPEP § 2143 (exemplary rationales for obviousness — the KSR rationales)
- MPEP § 2106 (subject matter eligibility — Alice/Mayo for § 101)
- MPEP § 2161–2163 (written description and enablement for § 112)
- MPEP § 714 (amendments and responses to office actions)
- MPEP § 706 (rejection of claims — form paragraphs)

**Verification:** After seeding, run a test retrieval:
```python
from src.retrieval.mpep_retriever import MPEPRetriever
retriever = MPEPRetriever()
results = retriever.search("KSR rationales for combining prior art references")
for r in results:
    print(f"MPEP § {r.section}: {r.text[:200]}")
```

You should see MPEP § 2143 results about the seven KSR exemplary rationales.

---

## Step 5: Seed sample patents

```bash
python scripts/seed_sample_patents.py
```

**What this should do:**
1. Fetch 100+ patents in TC 2100 (start with the cited references from your test office actions — these are the patents the examiner used, so they're the most immediately useful)
2. For each patent:
   - Fetch full specification text
   - Parse claims into independent/dependent structure
   - Chunk specification by section
   - Generate embeddings
   - Store in pgvector with metadata: `{patent_number, title, classification, section_type, claim_number, chunk_index}`

**Start small:** Don't try to seed 100 patents on day one. Start with the 5–10 cited references from your test office actions. Verify retrieval quality. Then expand.

**Seeding order:**
1. First: cited references from your test office actions (the patents the examiner relied on)
2. Second: the patent applications themselves (the inventions being examined)
3. Third: related patents in the same classification (for broader prior art coverage)

---

## Step 6: Run the full pipeline against a real office action

This is the moment of truth. Pick one of your test applications and run:

```bash
# If you have a CLI entry point:
python -m src.main analyze --application-number 16XXXXXX

# Or hit the API:
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"application_number": "16XXXXXX"}'
```

**What you're evaluating:**

1. **Did the OA parser correctly identify the rejection type?** (non-final, final)
2. **Did it correctly extract the rejection basis?** (§ 103, § 101, etc.)
3. **Did it correctly identify all cited references?** (patent numbers match)
4. **Did the citation verifier confirm the references exist in the USPTO database?**
5. **Are the claim-limitation mappings accurate?** (compare to your ground truth)
6. **What's the confidence score?** Is it calibrated? (high confidence on correct claims, low on uncertain ones)
7. **Are there any hallucinated claims?** (assertions not in the OA or cited references)

**Compare against your ground truth** for that application. Record:
- True positives (correct extractions)
- False positives (hallucinated or incorrect extractions)
- False negatives (things in the OA that the system missed)
- Verification status distribution (how many claims verified vs. flagged)

---

## Step 7: Iterate on parsing quality

The first live run will almost certainly reveal parsing issues. Common failure modes:

**Office action formatting varies wildly.** Some examiners write structured rejections with clear headers; others write paragraphs of prose. The two-stage parser (deterministic regex + LLM) should handle both, but the regex patterns may need tuning for real-world OAs.

**Claim limitation mapping is the hardest task.** The examiner might say "Smith teaches the claimed 'processor configured to receive interrupt signals' at col. 4, lines 23-45" — or they might say "the processor limitation is met by Smith" without specifying where. The system needs to handle both precision levels.

**Multiple rejection bases on the same claim.** A single claim can be rejected under § 103 AND § 101 AND § 112(b). The parser needs to handle this correctly.

**Alternative claim groupings.** Examiners often reject claims in groups: "Claims 1–4 are rejected under § 103 as obvious over Smith in view of Jones. Claims 5–8 are rejected under § 103 as obvious over Smith in view of Jones and further in view of Brown." The parser needs to handle claim ranges and grouped rejections.

**For each issue found:** Fix it, add a test case for it, re-run against all test applications.

---

## Step 8: Test response drafting

Once analysis is reliable, test the response drafter:

```bash
curl -X POST http://localhost:8000/api/v1/draft-response \
  -H "Content-Type: application/json" \
  -d '{"analysis_id": "xxx", "strategy": "argue"}'
```

**Evaluate the draft against these criteria:**
1. Does every argument cite a specific source? (patent passage, MPEP section)
2. Are the cited sources real and do they say what the draft claims?
3. Does the response address every rejected claim?
4. Are the arguments technically sound? (This is where your embedded systems expertise is essential — you can judge whether the technical distinctions are real)
5. What does the verification report show?

---

## Priority order summary

Do these in order. Each depends on the previous:

```
[ ] Step 0: Get USPTO API key (blocker — needs your USPTO.gov account + ID.me)
[~] Step 1: Validate USPTO client against live API  → run: python scripts/validate_uspto.py <appNum>
[ ] Step 2: Find 5 test applications, create ground truth
[~] Step 3: Start PostgreSQL + pgvector  → docker compose up -d db && python -m src.db.migrations
[~] Step 4: Seed MPEP (chapters 700, 2100, 2200)  → python scripts/seed_mpep.py
[ ] Step 5: Seed cited patents from test OAs
[~] Step 6: Run full pipeline on first real OA  → python -m src.main analyze --application-number <appNum>
[x] Step 7: Parser handles grouped/range/multi-basis rejections (offline tests added)
[ ] Step 8: Test response drafting
[ ] Step 9: Record hallucination metrics
```

`[~]` = code is ready and runnable; only Step 0 (the API key) blocks live execution.

### Offline prep landed (commit on top of Phase 1)

These were done without an API key so the steps run as soon as the key is in `.env`:

- **USPTO client** rewritten for the new ODP surface (`api.uspto.gov`, `X-Api-Key`): added
  `get_application`, `get_documents`, `get_office_action_text`, plus ODP `office-action`
  citations/rejections/enriched-citations endpoints, and application/patent-number
  normalization. Endpoint paths are centralized in `_Endpoints` for easy Swagger reconciliation.
- **Step 1 validator**: `scripts/validate_uspto.py` runs the metadata → documents → OA-text
  sequence and reports pass/fail.
- **Step 3**: `python -m src.db.migrations` applies `NNN_*.sql` idempotently
  (`schema_migrations` tracking table). DB naming unified to `atticus`.
- **DB credentials** live only in `.env` (`POSTGRES_*`); `docker-compose.yml` references them via
  `${...}` — nothing hardcoded.
- **Step 4**: `seed_mpep.py` now downloads chapters (best-effort) with local-file fallback.
- **Step 6**: CLI `python -m src.main analyze` (accepts `--application-number`, `--file`, or
  `--text`; `--no-llm` for deterministic-only).
- **Step 7**: the deterministic parser now expands `Claims 1-4`, `5, 7 and 9-11`, scopes cited
  references per rejection block, and emits one rejection per (claim, basis) so a claim rejected
  under multiple statutes is captured. Covered by `tests/unit/test_rejection_extraction.py`.

**Time estimate:** Steps 0–3 are infrastructure (1–2 days). Steps 4–5 are seeding (1 day). Steps 6–9 are iterative testing and fixing (3–5 days). Total: ~1 week to have Atticus running against live data with measured accuracy.

---

## Notes for Claude Code

When working through these steps with Claude Code, give it context:
- "Read CLAUDE.md for full architecture context"
- "Read NEXT_STEPS.md — we're on Step N"
- "The existing code structure is [describe what exists]"
- "The specific error/issue I'm hitting is [paste error]"

Claude Code should also know: the architecture doc is at `docs/trusted-legal-ai-architecture.md` and explains why each verification layer exists. If Claude Code suggests removing a verification step for simplicity, push back — those layers are there for a reason.

Also include the `trusted-legal-ai-architecture.md` in your `docs/` directory — both as a reference for yourself and as context for Claude Code when it needs to understand why the verification pipeline is designed the way it is.