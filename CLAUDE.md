# CLAUDE.md — Patent Prosecution AI Assistant

## Project identity

**Name:** Atticus (working title)
**What it is:** An AI-powered office action response assistant for embedded systems and computer architecture patents (USPTO Technology Centers 2100/2600).
**What it is NOT:** A general-purpose legal chatbot. Every output must trace to a verified source. No parametric generation for factual claims.

**Builder profile:** Solo developer with EE/CS background, embedded software experience, studying for the patent bar. This is a summer prototype — scope accordingly. Optimize for a working, demonstrable tool over feature completeness.

**Architecture reference:** See `docs/trusted-legal-ai-architecture.md` for the full seven-layer trust architecture this project implements.

---

## Core design principles

1. **Verification-first.** Every factual claim in any AI output must link to a retrievable source document. If it can't be sourced, it gets flagged — never silently passed through.
2. **Structured over free-form.** Office action analysis produces structured JSON objects (rejection type, cited references, claim mappings), not essays. Structure makes verification tractable.
3. **Closed-loop retrieval.** The LLM may only reference documents explicitly retrieved from verified sources (USPTO, MPEP). It must never supplement with training-data knowledge for any factual assertion about patents, cases, or procedures.
4. **Transparent uncertainty.** When confidence is low, say so. Show confidence scores. Highlight unverified claims in the UI. Never present a guess as a fact.
5. **Human-in-the-loop.** This tool drafts — the practitioner decides. Every output is editable, every assertion is reviewable with one click to its source.

---

## Tech stack

```
Language:        Python 3.11+
API framework:   FastAPI
Database:        PostgreSQL 16 + pgvector extension
Vector store:    pgvector (embedded in PostgreSQL — no separate vector DB needed for prototype)
LLM:             Anthropic Claude API (claude-sonnet-4-6 for generation, claude-haiku-4-5 for classification/verification)
Embeddings:      sentence-transformers (all-MiniLM-L6-v2 as baseline, upgrade to patent-tuned model later)
RAG framework:   Custom pipeline (not LangChain — keep dependencies minimal and logic transparent)
Frontend:        React + Tailwind CSS (simple SPA)
Containerization: Docker + docker-compose
Testing:         pytest + custom evaluation harness for hallucination measurement
CI:              GitHub Actions
```

**Why these choices:**
- PostgreSQL + pgvector keeps the stack simple (one database for structured data AND vector search) and is production-ready
- Custom RAG pipeline (not LangChain) because we need full control over retrieval, generation, and verification steps — abstraction layers hide the logic we need to audit
- Claude Sonnet for generation (best cost/quality ratio); Haiku for high-volume verification tasks (claim decomposition, entailment checking) where speed and cost matter
- sentence-transformers as baseline embeddings because they're free, fast, and good enough for prototype; plan to fine-tune on patent text later

---

## Directory structure

```
Atticus/
├── CLAUDE.md                          # This file — project prompt and plan
├── README.md                          # User-facing documentation
├── LICENSE                            # MIT or Apache 2.0
├── docker-compose.yml                 # PostgreSQL + pgvector + app
├── Dockerfile                         # App container
├── pyproject.toml                     # Python project config (use uv or poetry)
├── .env.example                       # Environment variable template
│
├── docs/
│   ├── trusted-legal-ai-architecture.md  # Seven-layer trust architecture reference
│   ├── api-reference.md               # API endpoint documentation
│   └── evaluation-methodology.md      # How we measure hallucination rates
│
├── src/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app entry point
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py                # Pydantic settings (API keys, DB URL, model config)
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── uspto_client.py            # USPTO Open Data Portal API client
│   │   ├── patent_fetcher.py          # Fetch patent full text, claims, specifications
│   │   ├── office_action_parser.py    # Parse office action text into structured format
│   │   └── mpep_indexer.py            # Index MPEP sections for retrieval
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py                 # Pydantic models for all data structures
│   │   ├── patent.py                  # Patent data model
│   │   ├── office_action.py           # Office action data model
│   │   ├── rejection.py               # Rejection analysis data model
│   │   └── response_draft.py          # Office action response draft model
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── embeddings.py              # Embedding generation and management
│   │   ├── vector_store.py            # pgvector operations (index, search, upsert)
│   │   ├── query_reformulator.py      # Transform user queries into effective retrieval queries
│   │   ├── patent_retriever.py        # Retrieve relevant patents and prior art
│   │   └── mpep_retriever.py          # Retrieve relevant MPEP sections
│   │
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── llm_client.py             # Anthropic API wrapper with retry logic
│   │   ├── prompt_templates.py        # All prompts — versioned, no inline strings
│   │   ├── oa_analyzer.py             # Office action analysis pipeline
│   │   ├── response_drafter.py        # Draft office action responses
│   │   └── claim_drafter.py           # Draft/amend patent claims
│   │
│   ├── verification/
│   │   ├── __init__.py
│   │   ├── claim_decomposer.py        # Break AI output into atomic verifiable claims
│   │   ├── citation_verifier.py       # Verify patent numbers exist in USPTO
│   │   ├── entailment_checker.py      # Check if source supports the claim made about it
│   │   ├── confidence_scorer.py       # Score each claim's verification status
│   │   └── hallucination_detector.py  # Orchestrate all verification layers
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── analyze.py             # POST /analyze — analyze an office action
│   │   │   ├── draft.py               # POST /draft — draft a response
│   │   │   ├── search.py              # POST /search — prior art search
│   │   │   ├── verify.py              # POST /verify — verify a claim or citation
│   │   │   └── health.py              # GET /health
│   │   └── middleware.py              # Logging, error handling, audit trail
│   │
│   └── db/
│       ├── __init__.py
│       ├── connection.py              # Database connection management
│       ├── migrations/                # Alembic or raw SQL migrations
│       └── repositories.py           # Data access layer
│
├── frontend/                          # React SPA
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── OfficeActionUpload.jsx     # Upload/paste office action text
│   │   │   ├── RejectionAnalysis.jsx      # Display parsed rejection structure
│   │   │   ├── ClaimMapping.jsx           # Show claim-by-claim examiner mapping
│   │   │   ├── ResponseDraft.jsx          # Editable AI-generated response draft
│   │   │   ├── VerificationPanel.jsx      # Show verification status per claim
│   │   │   ├── SourceViewer.jsx           # Display source document with highlighting
│   │   │   └── ConfidenceBadge.jsx        # Visual confidence indicator
│   │   └── api/
│   │       └── client.js                  # API client
│   └── tailwind.config.js
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_office_action_parser.py
│   │   ├── test_claim_decomposer.py
│   │   ├── test_citation_verifier.py
│   │   └── test_entailment_checker.py
│   ├── integration/
│   │   ├── test_analysis_pipeline.py
│   │   └── test_verification_pipeline.py
│   └── evaluation/
│       ├── hallucination_eval.py      # Measure hallucination rate on test set
│       ├── test_cases/                # Known office actions with ground-truth analyses
│       └── results/                   # Evaluation results (tracked in git)
│
├── scripts/
│   ├── seed_mpep.py                   # Download and index MPEP
│   ├── seed_sample_patents.py         # Fetch sample patents for TC 2100/2600
│   ├── run_evaluation.py             # Run hallucination evaluation suite
│   └── export_audit_trail.py          # Export audit logs for review
│
└── data/
    ├── mpep/                          # Cached MPEP text (gitignored, built by seed script)
    ├── sample_office_actions/         # Sample OAs for testing (committed)
    └── evaluation_ground_truth/       # Ground truth for eval (committed)
```

---

## Data models (implement these first)

### Office action analysis

```python
from pydantic import BaseModel
from enum import Enum
from typing import Optional

class RejectionBasis(str, Enum):
    SEC_101 = "101"           # Subject matter eligibility
    SEC_102 = "102"           # Novelty (anticipation)
    SEC_103 = "103"           # Obviousness
    SEC_112_A = "112(a)"      # Written description / enablement
    SEC_112_B = "112(b)"      # Definiteness
    DOUBLE_PATENTING = "dp"   # Double patenting

class CitedReference(BaseModel):
    patent_number: str                    # e.g., "US10,234,567"
    publication_number: Optional[str]     # e.g., "US2020/0123456"
    first_named_inventor: str
    title: Optional[str]
    relevant_passages: list[str]          # e.g., ["col. 4, lines 23-45", "Fig. 3"]
    verified: bool = False                # Set by citation_verifier
    verification_details: Optional[str]

class LimitationMapping(BaseModel):
    limitation_text: str                  # The claim limitation text
    mapped_to_reference: str              # Which reference the examiner maps it to
    reference_passage: str                # Where in the reference
    examiner_reasoning: Optional[str]     # The examiner's explanation
    source_span: Optional[str]            # Exact span in OA that supports this mapping

class ClaimRejection(BaseModel):
    claim_number: int
    rejection_basis: RejectionBasis
    is_independent: bool
    limitation_mappings: list[LimitationMapping]
    cited_references: list[CitedReference]

class OfficeActionAnalysis(BaseModel):
    application_number: str
    filing_date: Optional[str]
    examiner_name: Optional[str]
    art_unit: Optional[str]
    mailing_date: str
    rejection_type: str                   # "non-final", "final", "advisory"
    rejections: list[ClaimRejection]
    objections: list[str]                 # Claim objections (not rejections)
    requirements: list[str]              # Restriction requirements, election requirements
    raw_text: str                         # The original OA text for reference
    confidence_score: float               # 0-1 overall confidence in the analysis
    unverified_claims: list[str]          # List of claims that couldn't be verified
```

### Verification result

```python
class VerificationStatus(str, Enum):
    VERIFIED = "verified"               # Claim confirmed against source
    PARTIALLY_SUPPORTED = "partial"     # Source exists but doesn't fully support claim
    UNSUPPORTED = "unsupported"         # Source doesn't support the claim
    FABRICATED = "fabricated"            # Cited source doesn't exist
    UNVERIFIABLE = "unverifiable"       # Cannot be checked (e.g., subjective judgment)

class VerifiedClaim(BaseModel):
    claim_text: str                      # The atomic claim from the AI output
    claim_type: str                      # "citation", "legal_proposition", "factual", "procedural"
    status: VerificationStatus
    source_document: Optional[str]       # Document ID that was checked
    source_span: Optional[str]           # Exact text span in source
    confidence: float                    # 0-1
    explanation: str                     # Why this verification status was assigned

class VerificationReport(BaseModel):
    total_claims: int
    verified_count: int
    partial_count: int
    unsupported_count: int
    fabricated_count: int
    unverifiable_count: int
    overall_confidence: float
    claims: list[VerifiedClaim]
    needs_human_review: bool             # True if any claim is unsupported/fabricated
    review_flags: list[str]              # Specific items flagged for human attention
```

---

## Build phases

### Phase 1: Foundation (Weeks 1–3)

**Goal:** Data pipeline works. You can fetch a patent, fetch an office action, and parse it into structured data.

**Tasks:**
1. Set up project scaffolding (this directory structure, Docker, database)
2. Implement `uspto_client.py` — wrapper around the USPTO Open Data Portal API
   - Register for API key at data.uspto.gov
   - Implement patent application search by application number
   - Implement office action document retrieval
   - Implement patent full-text retrieval
   - Handle rate limiting, retries, and caching
3. Implement `office_action_parser.py` — parse raw office action text into structured `OfficeActionAnalysis`
   - Extract rejection type (non-final, final, advisory)
   - Extract rejection basis (§ 101, 102, 103, 112)
   - Extract cited references with patent numbers
   - Extract claim-by-claim limitation mappings
   - This is the hardest parsing task — office actions are semi-structured text. Use Claude to assist with parsing but validate the output structure.
4. Implement `patent_fetcher.py` — given a patent number, fetch and cache:
   - Full specification text
   - Claims (parsed into independent/dependent)
   - Figures metadata
   - Classification codes
5. Set up PostgreSQL with pgvector extension
6. Create initial database schema and migrations

**Acceptance criteria:** Given an application number with a known office action, the system can fetch the OA and produce a correct `OfficeActionAnalysis` JSON.

**Test with real data:** Use published applications in TC 2100 that have office actions with § 103 rejections. Start with 5 specific applications you've manually analyzed.

### Phase 2: Retrieval (Weeks 4–5)

**Goal:** Vector search works. Given a query about a patent concept, you can retrieve relevant patents, MPEP sections, and prior art.

**Tasks:**
1. Implement `embeddings.py` — generate embeddings for patent text
   - Start with `all-MiniLM-L6-v2` from sentence-transformers
   - Implement chunking strategy: chunk by claim (each claim = one chunk), chunk specification by section (description of drawings, detailed description, etc.)
   - Store embeddings in pgvector
2. Implement `mpep_indexer.py` — download and index relevant MPEP sections
   - Focus on: Chapter 2100 (patentability), Chapter 700 (examination of applications), Chapter 2200 (citation of prior art)
   - Chunk by section/subsection
   - Store in pgvector with metadata (MPEP section number, revision date)
3. Implement `vector_store.py` — pgvector operations
   - Upsert embeddings with metadata
   - Similarity search with filtering (by patent class, by document type, by date range)
   - Hybrid search: combine vector similarity with keyword/metadata filters
4. Implement `query_reformulator.py`
   - Take a natural language query or a claim limitation
   - Reformulate for effective patent search (expand acronyms, add synonyms, handle patent-specific terminology)
5. Implement `patent_retriever.py` and `mpep_retriever.py`
   - Top-k retrieval with configurable k
   - Return results with relevance scores
   - Include document metadata (patent number, section, date) for verification

**Acceptance criteria:** Given a claim limitation like "a processor configured to handle interrupt requests using a priority queue," the retriever returns relevant patents and MPEP sections.

**Seed data:** Run `scripts/seed_mpep.py` and `scripts/seed_sample_patents.py` to populate the database with at least:
- MPEP chapters 700, 2100, 2200
- 100+ patents in TC 2100 (computer architecture / embedded systems)
- Office actions for at least 20 of those patents

### Phase 3: Generation (Weeks 6–7)

**Goal:** The AI can analyze an office action and draft a response, grounded in retrieved context.

**Tasks:**
1. Implement `llm_client.py` — Anthropic API wrapper
   - Support for Claude Sonnet (generation) and Haiku (verification)
   - Retry logic with exponential backoff
   - Token counting and cost tracking
   - Structured output parsing (JSON mode)
2. Implement `prompt_templates.py` — ALL prompts in one place, versioned
   - `ANALYZE_OFFICE_ACTION` — parse an OA into structured analysis
   - `MAP_CLAIM_LIMITATIONS` — map examiner's rejection to specific claim limitations
   - `IDENTIFY_DISTINCTIONS` — identify technical distinctions between the invention and cited prior art
   - `DRAFT_RESPONSE_ARGUMENT` — draft an argument for why the rejection should be overcome
   - `SUGGEST_AMENDMENTS` — suggest claim amendments that distinguish over the prior art
   - Every prompt must include the instruction: "Base your response ONLY on the provided context. If the context does not contain sufficient information, say 'insufficient information' rather than speculating."
3. Implement `oa_analyzer.py` — the main analysis pipeline
   ```
   Input: application_number
   → Fetch office action from USPTO
   → Parse into OfficeActionAnalysis
   → For each cited reference: fetch the actual patent text
   → For each claim rejection: retrieve relevant MPEP sections
   → Generate structured analysis with source attribution
   → Return OfficeActionAnalysis with all fields populated
   ```
4. Implement `response_drafter.py` — draft office action response
   ```
   Input: OfficeActionAnalysis + user preferences (argue vs. amend)
   → For each rejected claim: retrieve the claim text, cited reference passages, and MPEP guidance
   → Generate response arguments grounded in the retrieved context
   → For each argument: include the specific source that supports it
   → Return structured draft with citations and confidence scores
   ```

**Critical constraint for ALL generation:**
Every prompt must enforce grounded generation. Use this pattern:

```python
SYSTEM_PROMPT = """You are a patent prosecution assistant. You MUST follow these rules:
1. Every factual claim you make must reference a specific document provided in the context.
2. Use the format [Source: document_id, location] for every factual assertion.
3. If the provided context does not contain information needed to answer, say "INSUFFICIENT_CONTEXT: [what's missing]" — do NOT fill in from your own knowledge.
4. Never invent patent numbers, case names, or MPEP section numbers.
5. When analyzing claim limitations, quote the exact text from the patent claims and cited references.
"""
```

**Acceptance criteria:** Given an office action with a § 103 rejection, the system produces an analysis that correctly identifies the rejection type, cited references, and claim mappings, with every assertion linked to a source.

### Phase 4: Verification (Weeks 8–9)

**Goal:** Every AI output passes through a verification pipeline. Users see verification status for each claim.

**Tasks:**
1. Implement `claim_decomposer.py`
   - Take an AI-generated response
   - Break it into atomic, verifiable claims
   - Classify each claim: citation, patent_reference, legal_proposition, factual_assertion, procedural_claim, opinion
   - Use Claude Haiku for decomposition (fast, cheap, good at classification)
2. Implement `citation_verifier.py`
   - For every patent number mentioned: query USPTO API to confirm it exists
   - For every patent passage cited (e.g., "col. 4, lines 23-45"): fetch that passage and confirm it contains what the AI claims
   - For every MPEP section cited: confirm the section exists and says what the AI claims
   - Return VerificationStatus for each citation
3. Implement `entailment_checker.py`
   - Given (source_text, claim_about_source), determine if the source actually supports the claim
   - Use Claude Haiku with a focused NLI prompt:
     ```
     Given the following source text and claim, determine if the source SUPPORTS, CONTRADICTS, or is NEUTRAL toward the claim.
     
     Source: {source_text}
     Claim: {claim_text}
     
     Respond with one of: ENTAILS, CONTRADICTS, NEUTRAL
     Explanation: [brief reason]
     ```
   - This catches the sneakiest hallucination type: real source, wrong characterization
4. Implement `confidence_scorer.py`
   - Aggregate verification results into overall confidence score
   - Apply rules: if ANY citation is fabricated, flag entire response for review
   - Weight by claim importance (a wrong patent number is worse than a slightly imprecise characterization)
5. Implement `hallucination_detector.py` — orchestrator
   - Run claim_decomposer → citation_verifier → entailment_checker → confidence_scorer
   - Produce VerificationReport
   - Log everything to audit trail

**Acceptance criteria:** When the AI generates a response with a fabricated patent number, the verification layer catches it and flags it. When the AI correctly cites a real patent but mischaracterizes its teaching, the entailment checker catches it.

### Phase 5: API and frontend (Weeks 10–11)

**Goal:** A usable web interface where a patent practitioner can analyze an office action and review the AI's work.

**API endpoints:**
```
POST /api/v1/analyze
  Input: { application_number: str } OR { office_action_text: str }
  Output: OfficeActionAnalysis with VerificationReport

POST /api/v1/draft-response
  Input: { analysis_id: str, strategy: "argue" | "amend" | "both" }
  Output: ResponseDraft with per-claim VerificationReport

POST /api/v1/search-prior-art
  Input: { query: str, filters: { tech_center, date_range, classification } }
  Output: list[PatentSearchResult] with relevance scores

POST /api/v1/verify-claim
  Input: { claim_text: str, cited_source: str }
  Output: VerifiedClaim

GET /api/v1/audit-trail/{analysis_id}
  Output: Complete audit trail for an analysis
```

**Frontend — key views:**

1. **Office action upload** — paste text or enter application number
2. **Rejection analysis view** — structured display of each rejection with:
   - Rejection basis (§ 103, etc.) with MPEP link
   - Cited references (each clickable to view the actual patent)
   - Claim limitation mapping (table: limitation → reference → passage)
   - Confidence badges on each element (green/yellow/red)
3. **Response draft view** — editable draft with:
   - Each argument with inline source citations
   - Verification panel showing per-claim status
   - Source viewer (click a citation → see the actual source text highlighted)
   - Accept/reject/edit controls per paragraph
4. **Audit trail view** — full transparency:
   - What was retrieved
   - What was generated
   - What was verified
   - What was flagged

### Phase 6: Evaluation and documentation (Week 12)

**Goal:** Measure actual hallucination rates. Document everything.

**Tasks:**
1. Create evaluation test set:
   - 20+ office actions from TC 2100/2600 with ground-truth analyses (you manually analyze these)
   - Include easy cases (straightforward § 103 rejections) and hard cases (mixed rejections, Alice § 101 issues)
   - Include adversarial cases (ask about non-existent patents, ask about rejections the OA doesn't contain)
2. Run evaluation:
   - Measure: citation accuracy, rejection-type accuracy, claim-mapping accuracy, hallucination rate (fabricated claims / total claims)
   - Compare: with vs. without verification layers
   - Document results in `docs/evaluation-methodology.md`
3. Write README.md with:
   - Project overview and motivation
   - Setup instructions
   - Architecture overview (reference the trust architecture doc)
   - Known limitations and failure modes
   - Evaluation results

---

## Prompt engineering guidelines

All prompts live in `src/generation/prompt_templates.py`. Follow these rules:

1. **System prompts set the constraint boundary.** Every system prompt must include the closed-loop instruction (only use provided context, never supplement with training knowledge).
2. **User prompts provide the context.** Include the full retrieved context in the user message, clearly delineated:
   ```
   <office_action>
   {full office action text}
   </office_action>
   
   <cited_reference ref="US10,234,567">
   {relevant passages from the cited reference}
   </cited_reference>
   
   <mpep section="2143">
   {relevant MPEP text}
   </mpep>
   
   <task>
   Analyze the § 103 rejection of claim 1. For each limitation, identify which reference the examiner maps it to and the specific passage cited.
   </task>
   ```
3. **Output format is always structured.** Request JSON output matching the Pydantic schema. Use Claude's structured output / tool-use features where possible.
4. **Version every prompt.** When you change a prompt, increment the version and keep the old version. This is essential for evaluation — you need to know which prompt version produced which results.
5. **Include negative examples.** In few-shot prompts, include examples of what NOT to do (e.g., "WRONG: The examiner cited Smith for the thermal management limitation. [No source provided]" → "RIGHT: The examiner cited Smith (col. 4, lines 23-45) for the thermal management limitation. [Source: OA paragraph 6]")

---

## Environment setup

```bash
# .env.example
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://patentpilot:password@localhost:5432/patentpilot
USPTO_API_KEY=your-key-from-data.uspto.gov
EMBEDDING_MODEL=all-MiniLM-L6-v2
GENERATION_MODEL=claude-sonnet-4-6
VERIFICATION_MODEL=claude-haiku-4-5
LOG_LEVEL=INFO
AUDIT_TRAIL_ENABLED=true
```

```yaml
# docker-compose.yml structure
services:
  db:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: patentpilot
      POSTGRES_USER: patentpilot
      POSTGRES_PASSWORD: password
    volumes:
      - pgdata:/var/lib/postgresql/data

  app:
    build: .
    ports: ["8000:8000"]
    depends_on: [db]
    env_file: .env
    volumes:
      - ./src:/app/src
      - ./data:/app/data

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [app]

volumes:
  pgdata:
```

---

## Critical implementation notes

### USPTO API specifics
- The Open Data Portal requires a free API key (register at data.uspto.gov)
- Rate limits apply — implement caching and respect rate limiting headers
- Office action text comes in semi-structured format — expect to handle inconsistent formatting
- Patent file wrapper data is available for applications filed after January 2001
- Bulk data downloads are available for larger-scale indexing

### Patent text chunking strategy
- **Claims:** Each claim = one chunk. Keep dependent claims linked to their parent independent claim.
- **Specification:** Chunk by section (background, summary, detailed description, drawings description). Within detailed description, chunk by paragraph but maintain reference to figures.
- **Office actions:** Chunk by rejection (each § 103 rejection of a specific claim set = one chunk). Keep the header (rejection basis, cited references) with each chunk.
- **MPEP:** Chunk by subsection. Maintain hierarchy metadata (chapter → section → subsection).

### Cost management
- Claude Sonnet: ~$3/M input tokens, $15/M output tokens
- Claude Haiku: ~$0.25/M input tokens, $1.25/M output tokens
- Use Haiku for all verification tasks (claim decomposition, entailment checking, citation classification) — these are high-volume, and Haiku is accurate enough
- Use Sonnet for analysis and response drafting where quality matters most
- Estimate: analyzing one office action end-to-end ≈ $0.50–$2.00 in API costs
- Cache embedding computations — don't re-embed documents you've already processed

### What NOT to build (scope control)
- ❌ User authentication / multi-tenancy (use a single-user prototype)
- ❌ Payment / billing
- ❌ International patent support (USPTO only for prototype)
- ❌ Patent drafting from invention disclosures (focus on prosecution response)
- ❌ Portfolio analytics
- ❌ Real-time USPTO monitoring
- ❌ Browser extension / Word plugin
- ❌ Mobile support

Focus on ONE workflow done well: office action analysis → response drafting → verification → human review.

---

## Success metrics

By end of summer, the prototype should demonstrate:

1. **Functional:** Given a real USPTO office action for an embedded systems patent, produce a structured analysis and draft response
2. **Accurate:** <5% hallucination rate on factual claims (measured against ground-truth test set)
3. **Traceable:** Every factual claim in the output links to a verifiable source
4. **Transparent:** Verification panel shows per-claim confidence with one-click source access
5. **Evaluated:** Documented hallucination rate measurement on 20+ test cases

---

## Getting started (first session with Claude Code)

Start here. Run these commands to scaffold the project:

```bash
mkdir patentpilot && cd patentpilot
git init
# Create the directory structure above
# Set up pyproject.toml with dependencies
# Set up docker-compose.yml
# Create .env.example
# Copy trusted-legal-ai-architecture.md to docs/
# Implement src/config/settings.py
# Implement src/data/uspto_client.py (start here — the data pipeline is everything)
```

Then: fetch your first real office action, parse it, and print the structured output. That's day one.