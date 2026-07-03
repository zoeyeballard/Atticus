# PHASE3_SPRINT.md — LLM Integration + Legal Compliance Architecture

## Context files to read first
- `CLAUDE.md` — core architecture, tech stack, design principles
- `NEXT_STEPS.md` — live validation results, API notes
- `docs/trusted-legal-ai-architecture.md` — seven-layer trust model

## Current state

Phase 2 complete. PostgreSQL + pgvector running. 655 MPEP chunks + 56 patent chunks indexed.
5 test applications validated with 100% deterministic parsing accuracy. 33 tests passing.
Evaluation harness built. All at $0 API cost.

**What's new this sprint:** We're wiring up the LLM (Anthropic API) and — critically — building
the legal compliance layer that determines what data we can store, where, and how. This isn't
an afterthought; it's a structural requirement that affects database schema, API design, and
every data flow in the system.

---

## PART A: Legal compliance framework

### Why this matters right now (not later)

Read this section carefully. It defines constraints that affect every technical decision below.

On February 17, 2026, Judge Jed Rakoff in the Southern District of New York ruled in
*United States v. Heppner* (25 Cr. 503) that documents generated using a consumer AI
platform are NOT protected by attorney-client privilege or the work product doctrine.
The court held that the AI platform's privacy policy — which permitted data collection,
model training, and disclosure to third parties — destroyed any reasonable expectation
of confidentiality. This is the first federal ruling directly on AI and privilege, and it
is being treated as highly persuasive authority nationwide.

**What this means for Atticus:** If a patent attorney uses our tool to analyze a client's
office action and draft a response, and we route that data through an AI API that retains
or trains on it, we have potentially destroyed attorney-client privilege for that entire
communication chain. That's not a privacy inconvenience — it's a malpractice exposure that
would make the tool unusable for any licensed practitioner.

### The two categories of data in Atticus

**Category 1: Public patent data (FREELY STORABLE)**

The USPTO explicitly defines its Open Data Portal content as open data that "can be freely
used, reused and redistributed by anyone" (USPTO ODP "Why Open Data?" page).

Under 37 CFR 1.11 and 1.14, the following are public records with no storage restrictions:
- Granted patents (full text, claims, specifications, drawings)
- Published patent applications (published under 35 U.S.C. 122(b))
- Office actions for published applications
- PTAB decisions
- MPEP text
- Patent classification data
- Examiner statistics and metadata

We CAN and SHOULD store, index, cache, and embed all of this data permanently in our
database. This is the knowledge base that makes Atticus useful. There is zero legal risk
in storing published patent data — it is literally designed to be public.

**Important limitation:** Unpublished patent applications are confidential under 35 U.S.C.
122(a) and 37 CFR 1.14(a). The ODP API only serves published data, so this is handled at
the source level — but our code must never attempt to access or store unpublished
application data. The system should verify publication status before indexing any
application.

**Category 2: Client-specific data (NEVER PERSIST WITHOUT SAFEGUARDS)**

When a practitioner uses Atticus to analyze THEIR CLIENT'S office action and draft a
response, that interaction generates privileged work product:
- The specific application being analyzed (if unpublished)
- The attorney's strategic decisions (argue vs. amend, which claims to prioritize)
- Draft response arguments
- Notes, annotations, and attorney mental impressions
- Prompt text containing client-specific facts or strategy

This data requires the following protections:

1. **Tenant isolation.** Each user/firm's client data must be completely isolated.
   No cross-user data leakage, ever. (For the prototype, single-user is fine, but
   the schema must support multi-tenancy from the start.)

2. **No training.** Client data must never be used to train, fine-tune, or improve
   any model — ours or a third party's.

3. **API data handling.** When we send client-specific content to the Anthropic API:
   - The Anthropic API (console.anthropic.com) does NOT use API inputs/outputs for
     model training by default. This is different from the consumer claude.ai product.
   - For production use, verify this by reading the current Anthropic API Terms of
     Service and Usage Policy.
   - For enterprise/production deployment, consider requesting Zero Data Retention
     (ZDR) from Anthropic, which ensures API inputs are not logged server-side.
   - NEVER route client data through the consumer claude.ai chat interface.

4. **Encryption at rest.** Client data stored in the database (analysis results,
   draft responses, audit trails) must be encrypted. For the prototype, document
   this as a requirement; implement before any real client data touches the system.

5. **Retention policy.** Client data should have a configurable retention period.
   Practitioners should be able to delete their analysis history. Implement a
   `DELETE /api/v1/analyses/{id}` endpoint that actually purges data (not soft-delete).

6. **Audit trail.** Log WHAT was sent to the LLM API (but store the audit trail in the
   same isolated, encrypted storage as client data — the audit trail itself is privileged).

### How this maps to the database schema

```sql
-- Public data: no access controls needed, permanent storage
CREATE TABLE public_patents (
    patent_number TEXT PRIMARY KEY,
    title TEXT,
    abstract TEXT,
    claims JSONB,
    specification TEXT,
    classification JSONB,
    filing_date DATE,
    grant_date DATE,
    -- This is public data; no tenant isolation needed
    indexed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public_patent_chunks (
    id SERIAL PRIMARY KEY,
    patent_number TEXT REFERENCES public_patents(patent_number),
    section_type TEXT,      -- 'claim', 'specification', 'abstract'
    claim_number INTEGER,
    chunk_index INTEGER,
    text TEXT,
    embedding vector(384),
    -- Public data; shared across all users
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE mpep_chunks (
    id SERIAL PRIMARY KEY,
    chapter TEXT,
    section TEXT,
    subsection TEXT,
    revision_date TEXT,
    chunk_index INTEGER,
    text TEXT,
    embedding vector(384),
    -- Public data; shared across all users
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Client data: tenant-isolated, encrypted, deletable
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,            -- Tenant isolation key
    application_number TEXT,
    analysis_result JSONB,              -- Structured parse output
    llm_enrichment JSONB,               -- LLM-enhanced analysis (if used)
    verification_report JSONB,          -- Verification results
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,             -- Retention policy
    -- Index for tenant isolation
    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);
CREATE INDEX idx_analyses_tenant ON analyses(tenant_id);

CREATE TABLE response_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    analysis_id UUID REFERENCES analyses(id) ON DELETE CASCADE,
    strategy TEXT,                       -- 'argue', 'amend', 'both'
    draft_content JSONB,
    verification_report JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);
CREATE INDEX idx_drafts_tenant ON response_drafts(tenant_id);

CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    event_type TEXT,                     -- 'api_call', 'analysis', 'verification'
    event_data JSONB,                   -- What happened (redact raw prompts in prod)
    llm_model TEXT,                     -- Which model was called
    token_count JSONB,                  -- {input: N, output: N, cost: $X.XX}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);
CREATE INDEX idx_audit_tenant ON audit_events(tenant_id);

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    retention_days INTEGER DEFAULT 90    -- Configurable retention
);
```

**For the prototype:** Create a single default tenant. The schema supports multi-tenancy
from day one, but we don't need authentication/authorization yet. Just ensure the
`tenant_id` column exists and is populated on every client-data row.

### Data flow diagram — what goes where

```
USER INPUT (application number or OA text)
    │
    ├─ Is this a published application? ──YES──► Fetch from USPTO (public)
    │       │                                         │
    │       │                                    Store in public_patents
    │       │                                    Index in public_patent_chunks
    │       │
    │       └─ Is this unpublished? ──YES──► REFUSE. Log warning.
    │                                        "Cannot analyze unpublished applications
    │                                         without proper authorization."
    │
    ├─ Parse OA (deterministic) ──► Store parse result in analyses (tenant-isolated)
    │
    ├─ Retrieve context (MPEP + patents) ──► Read from public tables (no client data)
    │
    ├─ LLM call (analysis/drafting) ──► Send to Anthropic API
    │       │                              │
    │       │                              ├─ System prompt: public (MPEP rules, format instructions)
    │       │                              ├─ Retrieved context: public (patent text, MPEP)
    │       │                              └─ User context: the OA text + claims being analyzed
    │       │                                  (this IS client-adjacent data in a real-world
    │       │                                   use case — handle with care)
    │       │
    │       └─ LLM response ──► Verify ──► Store in analyses/response_drafts (tenant-isolated)
    │
    └─ Audit trail ──► Store in audit_events (tenant-isolated)

CRITICAL RULE: Nothing from analyses, response_drafts, or audit_events
ever flows back into the public tables or the shared retrieval corpus.
Client work product stays in the client's tenant. Period.
```

---

## PART B: Technical tasks — LLM integration

### Task 1: Update database schema for data classification

Update `src/db/migrations` to implement the schema above. Key changes from the existing schema:

1. Add `tenants` table
2. Add `tenant_id` to `analyses`, `response_drafts`, `audit_events`
3. Separate `public_patents` / `public_patent_chunks` from `mpep_chunks`
   (these may already be separate — verify and align naming)
4. Add `expires_at` to client-data tables
5. Add indexes for tenant isolation
6. Create a default tenant for prototype use

```bash
python -m src.db.migrations
```

**Acceptance criteria:** Schema migrated. All existing data preserved. Default tenant created.
All client-data tables have `tenant_id` column. All queries in the codebase that touch
client-data tables include a `WHERE tenant_id = :tenant_id` clause.

### Task 2: Add data classification to the config

```python
# src/config/data_classification.py
"""
Data classification rules for Atticus.
Determines what can be stored where and how.
"""
from enum import Enum

class DataClass(str, Enum):
    PUBLIC = "public"           # Published patents, MPEP, granted patents
    CLIENT = "client"           # Analysis results, drafts, audit trails
    PRIVILEGED = "privileged"   # Attorney work product, strategy decisions

class StoragePolicy:
    """Rules for each data classification."""

    PUBLIC = {
        "can_persist": True,
        "can_share_across_tenants": True,
        "can_use_for_retrieval": True,
        "encryption_required": False,  # Public data; encrypt if convenient
        "retention": None,             # Permanent
        "can_send_to_llm": True,       # Safe to include in prompts
    }

    CLIENT = {
        "can_persist": True,
        "can_share_across_tenants": False,  # NEVER cross tenant boundaries
        "can_use_for_retrieval": False,     # Never index client data for other users
        "encryption_required": True,        # Required before production use
        "retention": 90,                    # Days; configurable per tenant
        "can_send_to_llm": True,            # Via API with no-training terms only
    }

    PRIVILEGED = {
        "can_persist": False,           # Minimize persistence of privileged content
        "can_share_across_tenants": False,
        "can_use_for_retrieval": False,
        "encryption_required": True,
        "retention": 30,                # Shorter retention for privileged materials
        "can_send_to_llm": True,        # With extra caution; log the fact, not content
    }


def classify_data(source: str) -> DataClass:
    """Classify data by its source."""
    public_sources = {
        "uspto_published_patent",
        "uspto_published_application",
        "uspto_office_action",          # OAs for published apps are public
        "mpep",
        "ptab_decision",
        "patent_classification",
    }
    if source in public_sources:
        return DataClass.PUBLIC

    # Everything from user interaction is client data at minimum
    return DataClass.CLIENT
```

### Task 3: Implement publication status check

Before indexing any application, verify it has been published:

```python
# In src/data/uspto_client.py — add or update this method

def is_published(self, application_number: str) -> bool:
    """
    Check if a patent application has been published.
    Only published applications and their associated documents
    may be stored and indexed. Unpublished applications are
    confidential under 35 U.S.C. 122(a) and 37 CFR 1.14(a).
    """
    app_data = self.get_application(application_number)
    if not app_data:
        return False

    # Check for publication number or granted patent number
    has_publication = bool(app_data.get("publicationNumber"))
    has_patent = bool(app_data.get("patentNumber"))
    status = app_data.get("applicationStatusCategory", "")

    # Published applications have a publication number or have been patented
    return has_publication or has_patent or status == "Patented"
```

Add a guard in the analysis pipeline:

```python
# In the analyze endpoint or pipeline entry point
def analyze_application(application_number: str, tenant_id: str, allow_unpublished: bool = False):
    if not allow_unpublished:
        if not uspto_client.is_published(application_number):
            raise ValueError(
                f"Application {application_number} does not appear to be published. "
                "Unpublished applications are confidential under 35 U.S.C. 122(a). "
                "Atticus only indexes published patent data. "
                "If you have authorization to access this application, "
                "use --allow-unpublished with appropriate documentation."
            )
    # ... proceed with analysis
```

**Acceptance criteria:** Attempting to analyze an unpublished application raises a clear
error. The --allow-unpublished flag exists for authorized users but defaults to off.

### Task 4: Wire up Anthropic API with cost controls and audit logging

Update `src/generation/llm_client.py`:

1. **Verify the API key works.** Run `scripts/validate_anthropic.py` — it should
   make a minimal API call and confirm billing is active.

2. **Add per-run cost tracking and hard budget cap:**
   ```python
   class LLMClient:
       def __init__(self, settings):
           self.max_cost_per_run = settings.MAX_COST_PER_RUN_USD  # e.g., 5.00
           self.current_run_cost = 0.0

       def call(self, messages, model=None, ...):
           # ... make API call ...
           cost = self._calculate_cost(input_tokens, output_tokens, model)
           self.current_run_cost += cost
           if self.current_run_cost > self.max_cost_per_run:
               raise BudgetExceededError(
                   f"Run cost ${self.current_run_cost:.2f} exceeds "
                   f"budget ${self.max_cost_per_run:.2f}"
               )
           # ... return result ...
   ```

3. **Add audit logging for every LLM call:**
   ```python
   def _log_api_call(self, tenant_id, model, input_tokens, output_tokens, cost, purpose):
       """Log the API call metadata. Do NOT log raw prompt content in production."""
       audit_event = {
           "event_type": "llm_api_call",
           "model": model,
           "input_tokens": input_tokens,
           "output_tokens": output_tokens,
           "cost_usd": cost,
           "purpose": purpose,  # "analysis", "verification", "drafting"
           "timestamp": datetime.utcnow().isoformat(),
           # In production: DO NOT log the full prompt — it may contain
           # client-privileged content. Log only metadata.
       }
       self.audit_repository.save(tenant_id, audit_event)
   ```

4. **Use appropriate models for each task:**
   - `claude-sonnet-4-6` for analysis and response drafting (quality matters)
   - `claude-haiku-4-5` for verification tasks (claim decomposition, entailment
     checking, citation classification) — high volume, cost-sensitive

5. **Enable prompt caching** for the system prompt and MPEP context (these are
   static across calls and benefit from 90% cache discount).

**Add to .env:**
```
GENERATION_MODEL=claude-sonnet-4-6
VERIFICATION_MODEL=claude-haiku-4-5
MAX_COST_PER_RUN_USD=5.00
ENABLE_PROMPT_CACHING=true
```

### Task 5: Run LLM-enriched analysis on test applications

With the API wired up, run the full pipeline (not `--no-llm`) against our 5 test
applications:

```bash
for a in 19531961 19445647 19418983 19406513 19025078; do
  python -m src.main analyze --application-number $a \
    --output-json results/${a}_full_analysis.json
done
```

**Compare against the deterministic baseline:**
- Does LLM enrichment ADD useful information? (e.g., richer limitation mappings,
  identified arguments, suggested distinctions)
- Does LLM enrichment INTRODUCE errors? (hallucinated references, wrong claim
  mappings, invented statutory bases)
- What's the verification report for each analysis? How many claims verify vs. flag?

Run the scoring:
```bash
python scripts/score_parsing.py --mode full
python scripts/run_evaluation.py --mode full
```

Record the hallucination rate: fabricated claims / total claims.

### Task 6: Run verification pipeline on LLM outputs

For each LLM-enriched analysis:

1. **Claim decomposition** — break LLM output into atomic claims (Haiku)
2. **Citation verification** — confirm every patent number exists in USPTO (API call)
3. **Entailment checking** — confirm every source actually supports the claim (Haiku)
4. **Confidence scoring** — aggregate into per-claim and overall scores

```bash
python -m src.main verify --analysis-id <id>
```

**Key metrics to record:**
- Total claims generated by LLM
- Claims verified (source confirmed, entailment confirmed)
- Claims partially supported
- Claims unsupported (source exists but doesn't say what LLM claims)
- Claims fabricated (source doesn't exist)
- Claims unverifiable (subjective judgment, no factual check possible)

### Task 7: Test response drafting

```bash
for a in 19531961 19445647 19418983 19406513 19025078; do
  python -m src.main draft-response --analysis-id <id> --strategy argue \
    --output-json results/${a}_draft.json
done
```

**Evaluate each draft:**
1. Does every argument cite a specific, real source?
2. Does the entailment checker confirm the citations?
3. Are the arguments technically sound? (Use your EE expertise)
4. Does the draft address every rejected claim?
5. Does the verification report flag anything?

### Task 8: Add legal compliance documentation

Create `docs/data-handling-policy.md` in the repo:

```markdown
# Atticus Data Handling Policy

## Data Classification

### Public Data (freely storable)
- Published patents and patent applications (37 CFR 1.11)
- Office actions for published applications (37 CFR 1.14(a)(1)(iii))
- MPEP text (U.S. government work, no copyright)
- PTAB decisions
- Patent classification data

**Legal basis:** USPTO Open Data Portal content is explicitly designated as open data
that "can be freely used, reused and redistributed by anyone."

### Client Data (tenant-isolated, encrypted, retention-limited)
- Analysis results generated for a specific user/firm
- Response drafts
- User annotations and strategic decisions
- Audit trails of AI interactions

**Legal basis:** Attorney-client privilege requires confidentiality.
Per *U.S. v. Heppner* (S.D.N.Y. Feb. 17, 2026), AI-generated legal documents
lose privilege protection when the AI platform's terms permit data retention,
training, or third-party disclosure. Atticus mitigates this by:
1. Using the Anthropic API (not consumer products) which does not train on
   API inputs by default
2. Isolating client data by tenant
3. Never cross-pollinating client data into shared indexes
4. Supporting configurable retention and hard deletion

### Unpublished Applications (do not access)
- Unpublished pending applications are confidential under 35 U.S.C. 122(a)
- Atticus verifies publication status before indexing
- Unpublished application data is never stored

## AI API Data Handling
- All LLM calls use the Anthropic Messages API (not consumer chat)
- Anthropic's API terms state that API inputs are not used for model training
- For production/enterprise deployment: obtain Zero Data Retention (ZDR) agreement
- Client-specific content in prompts is classified as CLIENT data
- System prompts and public context (MPEP, published patents) are PUBLIC data

## Professional Responsibility Alignment
- ABA Model Rule 1.1 (Competence): Atticus provides verification reports so
  practitioners can competently review AI outputs
- ABA Model Rule 1.6 (Confidentiality): Client data is tenant-isolated and
  never shared or used for training
- ABA Model Rules 5.1/5.3 (Supervision): Atticus is designed as a drafting
  assistant under attorney supervision, not an autonomous agent
```

### Task 9: Update evaluation harness with compliance checks

Add compliance validation to the evaluation harness:

```python
# In scripts/run_evaluation.py — add compliance checks

def check_data_compliance(analysis_result):
    """Verify that the analysis respects data classification rules."""
    issues = []

    # Check: no unpublished application data stored
    if not analysis_result.get("publication_verified", False):
        issues.append("CRITICAL: Publication status not verified before indexing")

    # Check: tenant_id present on all client data
    if not analysis_result.get("tenant_id"):
        issues.append("CRITICAL: Missing tenant_id on client data")

    # Check: all cited patents are real (no hallucinated references in public store)
    for ref in analysis_result.get("cited_references", []):
        if ref.get("verification_status") == "fabricated":
            issues.append(f"CRITICAL: Fabricated reference {ref['patent_number']} — "
                          "must not be stored in public patent index")

    # Check: audit trail exists for LLM calls
    if analysis_result.get("llm_used") and not analysis_result.get("audit_events"):
        issues.append("WARNING: LLM used but no audit trail recorded")

    return issues
```

---

## PART C: UI / Web application

### Design philosophy

Atticus is a tool for patent practitioners — people who bill in six-minute increments, work
in Word, think in claim charts, and will not adopt software that adds friction to their
workflow. The UI must be designed around how they already work, not around how the
backend pipeline is structured.

**Core principles for the Atticus UI:**

1. **Document-centric, not dashboard-centric.** Lawyers think in documents: the office
   action, the response, the claim set. The UI should feel like working with a smart
   document, not navigating a data platform. No analytics dashboards, no charts, no
   metrics on the primary screens. The document IS the interface.

2. **Progressive disclosure.** Show the summary first. Let the practitioner drill into
   details on demand. The rejection summary should be readable in 10 seconds; the
   claim-by-claim analysis available one click deeper; the source text available one
   click beyond that. Three levels, never more.

3. **Trust signals, not tech signals.** Display "Verified — Source: Smith, col. 4,
   lines 23–45" not "Entailment score: 0.87, NLI confidence: HIGH." The verification
   badge vocabulary should be: Verified (green), Review Suggested (amber), Unverified
   (red), Not Applicable (gray). Practitioners understand trust levels; they don't
   understand ML metrics.

4. **No jargon.** The UI never mentions "RAG," "embeddings," "tokens," "hallucination
   rate," or "LLM." It uses: "AI-assisted analysis," "source verification," "confidence
   level," "draft response." The technology is invisible; the value is visible.

5. **Export to Word.** Every analysis and every draft response must be exportable as a
   .docx file. This is non-negotiable. Lawyers file responses in Word. They review drafts
   in Word. They send work product to clients in Word. If the output can't get into Word
   in one click, the tool is broken for its actual users.

6. **Professional, quiet visual design.** Think Westlaw + Linear, not Figma + Notion.
   Muted palette. Serif or transitional serif for headings (this is a legal tool — serif
   conveys authority and precision). Clean sans-serif for body. Generous whitespace.
   No gradients, no rounded cards with shadows, no playful illustrations. The aesthetic
   is: a well-formatted legal memorandum that happens to be interactive.

### Color and typography direction

```
Palette:
  --bg-primary:       #FAFAF9       Warm white paper
  --bg-secondary:     #F5F5F4       Subtle section backgrounds
  --bg-sidebar:       #1C1917       Dark sidebar (stone-900)
  --text-primary:     #1C1917       Near-black body text
  --text-secondary:   #57534E       Muted secondary text (stone-600)
  --accent:           #1E40AF       Deep blue for links and actions (blue-800)
  --accent-hover:     #1E3A8A       Darker blue on hover (blue-900)
  --verified:         #166534       Confidence green (green-800)
  --review:           #92400E       Amber for review-needed (amber-800)
  --unverified:       #991B1B       Red for unverified (red-800)
  --border:           #D6D3D1       Subtle borders (stone-300)

Typography:
  Display/headings:   'Merriweather', Georgia, serif — weight 700
  Body text:          'Inter', system-ui, sans-serif — weight 400/500
  Monospace (claims):  'JetBrains Mono', 'Courier New', monospace — for claim text,
                       patent references, statutory citations
  Scale:              text-sm (13px) body, text-base (15px) for primary content,
                      text-lg (18px) section headers, text-xl (22px) page titles
```

### Application structure — 5 views

```
┌─────────────────────────────────────────────────────────┐
│  ATTICUS                                                │
│  ┌──────────┐  ┌───────────────────────────────────┐    │
│  │ Sidebar  │  │  Main Content Area                │    │
│  │          │  │                                   │    │
│  │ ● New    │  │  (one of the 5 views below)      │    │
│  │   Analysis│  │                                   │    │
│  │          │  │                                   │    │
│  │ Recent:  │  │                                   │    │
│  │  App 195.│  │                                   │    │
│  │  App 194.│  │                                   │    │
│  │  App 190.│  │                                   │    │
│  │          │  │                                   │    │
│  │          │  │                                   │    │
│  │ ─────── │  │                                   │    │
│  │ Settings │  │                                   │    │
│  └──────────┘  └───────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

#### View 1: New Analysis (the entry point)

This is where the practitioner starts. Keep it dead simple.

```
┌─────────────────────────────────────────┐
│                                         │
│   Analyze an Office Action              │
│                                         │
│   ┌─────────────────────────────────┐   │
│   │  Enter application number       │   │
│   │  ┌───────────────────────────┐  │   │
│   │  │ 19531961                  │  │   │
│   │  └───────────────────────────┘  │   │
│   │          [ Analyze ]            │   │
│   └─────────────────────────────────┘   │
│                                         │
│   ── or ──                              │
│                                         │
│   ┌─────────────────────────────────┐   │
│   │  Paste office action text       │   │
│   │  ┌───────────────────────────┐  │   │
│   │  │                           │  │   │
│   │  │  (large textarea)         │  │   │
│   │  │                           │  │   │
│   │  └───────────────────────────┘  │   │
│   │          [ Analyze ]            │   │
│   └─────────────────────────────────┘   │
│                                         │
│   ┌─────────────────────────────────┐   │
│   │  Or upload a .docx file         │   │
│   │       [ Choose File ]           │   │
│   └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

**Implementation notes:**
- Three input methods: application number (fetches from USPTO), paste text, upload DOCX
- When analyzing by application number, show a loading state with real progress:
  "Fetching from USPTO..." → "Parsing office action..." → "Verifying references..."
  → "Analysis complete"
- If the application is unpublished, show a clear message explaining why it can't be
  analyzed (per the compliance framework in Part A)

#### View 2: Analysis Overview (the main working screen)

After analysis completes, show the structured result. This is where practitioners
spend most of their time. The layout is a three-panel design:

```
┌──────────────────────────────────────────────────────────────┐
│  App 19,531,961 — Non-Final Rejection — Art Unit 2172       │
│  Examiner: [name]  •  Mailed: [date]  •  Response due: [d]  │
│  ┌────────────────┐                                          │
│  │ [Draft Response]│  [Export Analysis]  [View Raw OA]       │
│  └────────────────┘                                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  REJECTIONS                                                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ §103 — Obviousness                        ● Verified │   │
│  │ Claims 25–27, 32                                     │   │
│  │ Primary: Smith (US 10,234,567)                       │   │
│  │ Secondary: Jones (US 11,345,678)                     │   │
│  │                                          [Expand ▾]  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ §102 — Anticipation                       ● Verified │   │
│  │ Claims 21–24, 33–36                                  │   │
│  │ Reference: Brown (US 9,876,543)                      │   │
│  │                                          [Expand ▾]  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ §112(b) — Indefiniteness                  ● Verified │   │
│  │ Claims 33–36                                         │   │
│  │ Issue: "processing unit" lacks antecedent basis      │   │
│  │                                          [Expand ▾]  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**When a rejection card is expanded:**

```
┌──────────────────────────────────────────────────────────────┐
│ §103 — Obviousness                               ● Verified │
│ Claims 25–27, 32                                             │
│ Primary: Smith (US 10,234,567)                               │
│ Secondary: Jones (US 11,345,678)                             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CLAIM 25 (independent)                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Limitation                │ Mapped to     │ Status     │ │
│  ├────────────────────────────┼───────────────┼────────────┤ │
│  │ "a processor configured   │ Smith,        │ ● Verified │ │
│  │  to receive interrupt     │ col. 4,       │            │ │
│  │  signals"                 │ ln 23–45      │ [View ↗]   │ │
│  ├────────────────────────────┼───────────────┼────────────┤ │
│  │ "a priority queue stored  │ Jones,        │ ◐ Review   │ │
│  │  in non-volatile memory"  │ Fig. 3,       │            │ │
│  │                           │ ¶ [0045]      │ [View ↗]   │ │
│  ├────────────────────────────┼───────────────┼────────────┤ │
│  │ "wherein the processor    │ Smith+Jones   │ ● Verified │ │
│  │  executes a scheduling    │ combination,  │            │ │
│  │  algorithm"               │ col. 7, ln 1  │ [View ↗]   │ │
│  └────────────────────────────┴───────────────┴────────────┘ │
│                                                              │
│  CLAIM 26 (depends from 25)                                  │
│  [similar table...]                                          │
│                                                              │
│  MPEP GUIDANCE                                               │
│  Per MPEP § 2143, the examiner must establish one of the     │
│  KSR exemplary rationales for combining references.          │
│  The OA cites: "combining prior art elements according to    │
│  known methods to yield predictable results"                 │
│  Identified rationale: KSR Exemplary Rationale (A)           │
│                                                              │
│                     [Draft Response for This Rejection →]    │
└──────────────────────────────────────────────────────────────┘
```

**The [View ↗] button** opens the Source Viewer (View 4) showing the exact passage
from the cited patent with the relevant text highlighted. This is the one-click
verification that practitioners need.

#### View 3: Response Draft Editor

When the practitioner clicks "Draft Response," the system generates a response
draft and presents it in an editable format:

```
┌──────────────────────────────────────────────────────────────┐
│  Response Draft — App 19,531,961                             │
│  Strategy: Argue distinctiveness  •  Addressing: §103        │
│                                                              │
│  ┌─── Strategy ─────────────────────────────────────────┐   │
│  │ ○ Argue (distinguish over prior art)                 │   │
│  │ ○ Amend (narrow claims)                              │   │
│  │ ○ Both (argue + propose amendments)                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─── Draft ────────────────────────────── ● Verified ──┐   │
│  │                                                       │   │
│  │  REMARKS                                              │   │
│  │                                                       │   │
│  │  Claims 25–27 and 32 stand rejected under 35 U.S.C.  │   │
│  │  § 103 as allegedly obvious over Smith (US            │   │
│  │  10,234,567) in view of Jones (US 11,345,678).       │   │
│  │  Applicant respectfully traverses.                    │   │
│  │                                                       │   │
│  │  The Examiner asserts that Smith discloses "a         │   │
│  │  processor configured to receive interrupt signals"   │   │
│  │  at col. 4, lines 23–45. [● Verified] Applicant      │   │
│  │  submits that Smith's disclosure is directed to a     │   │
│  │  general-purpose interrupt controller, not the        │   │
│  │  claimed priority-aware scheduling mechanism. [...]   │   │
│  │                                                       │   │
│  │  (editable rich text — practitioner modifies freely)  │   │
│  │                                                       │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─── Sources cited in this draft ───────────────────────┐  │
│  │ Smith (US 10,234,567) col. 4, ln 23–45    ● Verified │  │
│  │ Jones (US 11,345,678) Fig. 3, ¶ [0045]    ● Verified │  │
│  │ MPEP § 2143(A) — KSR Rationale (A)        ● Verified │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  [ Export to Word ]   [ Copy Text ]   [ Save Draft ]        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Key features:**
- Rich text editor for the draft (use a lightweight editor like Tiptap or Lexical)
- Inline verification badges next to each sourced claim
- Practitioner can freely edit the text — AI provides the first draft, human refines
- Source panel on the side or bottom showing all cited sources
- Export to .docx preserves formatting and includes the source citations as footnotes

#### View 4: Source Viewer (slide-out panel)

When the practitioner clicks [View ↗] on any source citation, a slide-out panel
shows the actual source text with the relevant passage highlighted:

```
┌────────────────────────────────────────────────┐
│  Source: Smith (US 10,234,567)                 │
│  Column 4, Lines 23–45                    [×]  │
├────────────────────────────────────────────────┤
│                                                │
│  ...The interrupt controller 302 receives      │
│  incoming signals from peripheral bus 304.     │
│  ┌──────────────────────────────────────────┐  │
│  │ When an interrupt is detected, the       │  │
│  │ controller evaluates the priority level  │  │
│  │ assigned to each interrupt source and    │  │
│  │ routes the highest-priority signal to    │  │
│  │ the processing unit via dedicated        │  │
│  │ register 306.                            │  │
│  └──── highlighted: examiner's cited text ──┘  │
│  The processing unit then saves the current    │
│  execution context to stack memory 308         │
│  before servicing the interrupt...             │
│                                                │
│  ── Examiner's assertion ──                    │
│  "Smith discloses a processor configured to    │
│   receive interrupt signals"                   │
│                                                │
│  ── Verification ──                            │
│  ● Verified: The cited passage does describe   │
│  interrupt signal reception by a processing    │
│  unit, consistent with the examiner's mapping. │
│                                                │
│  ── Your claim limitation ──                   │
│  "a processor configured to receive interrupt  │
│   signals from a priority queue stored in      │
│   non-volatile memory"                         │
│                                                │
│  ⚡ Key distinction: Smith's interrupt          │
│  controller uses volatile registers (306),     │
│  not non-volatile memory as claimed.           │
│                                                │
└────────────────────────────────────────────────┘
```

**This is the view that builds trust.** The practitioner sees exactly what the AI
is basing its analysis on, can read the source text themselves, and can immediately
judge whether the mapping is correct. One click from assertion to source.

#### View 5: Settings

Minimal settings page:

```
┌─────────────────────────────────────────┐
│  Settings                               │
│                                         │
│  API Configuration                      │
│  Anthropic API Key: ●●●●●●●●sk-a..     │
│  USPTO API Key: ●●●●●●●●abc..          │
│                                         │
│  Analysis Preferences                   │
│  Default strategy: [Argue ▾]            │
│  AI enrichment:    [Enabled ▾]          │
│  Auto-verify:      [Enabled ▾]          │
│                                         │
│  Data & Privacy                         │
│  Retention period:  [90 days ▾]         │
│  [ Delete All My Analysis Data ]        │
│                                         │
│  Cost Tracking                          │
│  This month: $4.23                      │
│  Per-run budget cap: [$5.00]            │
│                                         │
└─────────────────────────────────────────┘
```

### Task 10: Set up React frontend with routing and layout shell

Build the application shell with React Router and the sidebar layout.

**Tech stack for frontend:**
- React 18+ (already in the project from Phase 1)
- React Router v6 for navigation
- Tailwind CSS for styling
- Tiptap or Lexical for the rich text editor in the response draft view
- react-hot-toast for notifications
- Import Google Fonts: Merriweather (serif display) and Inter (sans body)

**File structure:**

```
frontend/src/
├── App.jsx                      # Router + layout shell
├── index.css                    # Tailwind base + custom tokens (palette above)
├── api/
│   └── client.js               # Axios/fetch wrapper for backend API
├── components/
│   ├── layout/
│   │   ├── Sidebar.jsx          # Dark sidebar with nav + recent analyses
│   │   ├── MainContent.jsx      # Content area wrapper
│   │   └── PageHeader.jsx       # Page title + action buttons
│   ├── analysis/
│   │   ├── NewAnalysis.jsx      # Entry form (3 input methods)
│   │   ├── AnalysisOverview.jsx # Main analysis view with rejection cards
│   │   ├── RejectionCard.jsx    # Collapsible rejection summary
│   │   ├── ClaimMappingTable.jsx# Claim-by-claim limitation mapping
│   │   └── AnalysisLoading.jsx  # Progress indicator during analysis
│   ├── drafting/
│   │   ├── ResponseDraft.jsx    # Editable draft with strategy selector
│   │   ├── DraftEditor.jsx      # Rich text editor component
│   │   └── SourcePanel.jsx      # Sources cited in the draft
│   ├── verification/
│   │   ├── VerificationBadge.jsx    # Green/amber/red trust indicator
│   │   ├── SourceViewer.jsx         # Slide-out panel with source text
│   │   └── VerificationSummary.jsx  # Summary stats for an analysis
│   ├── export/
│   │   └── ExportButton.jsx     # Export to .docx
│   └── common/
│       ├── LoadingSpinner.jsx
│       ├── ErrorBoundary.jsx
│       └── EmptyState.jsx       # Friendly empty states
├── pages/
│   ├── NewAnalysisPage.jsx
│   ├── AnalysisPage.jsx         # /analysis/:id
│   ├── DraftPage.jsx            # /analysis/:id/draft
│   └── SettingsPage.jsx
├── hooks/
│   ├── useAnalysis.js           # Fetch + cache analysis data
│   ├── useDraft.js              # Draft state management
│   └── useVerification.js       # Verification data fetching
└── utils/
    ├── formatters.js            # Patent number formatting, date formatting
    ├── claimParser.js           # Parse claim text for display
    └── exportDocx.js            # Generate .docx from analysis/draft
```

**Implementation:**

```jsx
// App.jsx — the application shell
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import MainContent from './components/layout/MainContent';
import NewAnalysisPage from './pages/NewAnalysisPage';
import AnalysisPage from './pages/AnalysisPage';
import DraftPage from './pages/DraftPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-[#FAFAF9]">
        <Sidebar />
        <MainContent>
          <Routes>
            <Route path="/" element={<NewAnalysisPage />} />
            <Route path="/analysis/:id" element={<AnalysisPage />} />
            <Route path="/analysis/:id/draft" element={<DraftPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </MainContent>
      </div>
    </BrowserRouter>
  );
}
```

**Acceptance criteria:** App renders with sidebar, routing works between all 4 pages,
dark sidebar with navigation links, custom typography loaded, color tokens applied.

### Task 11: Build the New Analysis page

The entry point. Three input methods: application number, paste text, upload file.

**Behavior:**
- Application number input: validate format (8-digit number), then POST to
  `/api/v1/analyze` with `{ application_number: "19531961" }`
- Text paste: large textarea, POST to `/api/v1/analyze` with `{ office_action_text: "..." }`
- File upload: accept .docx and .txt, extract text client-side or send to backend,
  POST to `/api/v1/analyze` with `{ office_action_text: extracted_text }`
- Show real-time progress during analysis:
  - "Fetching from USPTO..." (if by application number)
  - "Parsing office action..."
  - "Verifying references..."
  - "Generating analysis..." (if LLM enrichment enabled)
  - "Analysis complete" → redirect to `/analysis/:id`

**Error states to handle:**
- Invalid application number format
- Application not found in USPTO
- Application is unpublished (show clear explanation per compliance rules)
- USPTO API timeout
- Network errors

**Acceptance criteria:** All three input methods work. Progress is shown during analysis.
Errors are handled gracefully with clear, non-technical messages. On completion,
navigates to the analysis view.

### Task 12: Build the Analysis Overview page

The main working screen. Shows the structured rejection analysis.

**Data flow:**
- Fetch analysis from `GET /api/v1/analyses/:id`
- Render rejection cards (collapsed by default)
- Each card shows: statutory basis, affected claims, cited references, verification badge
- Expanding a card shows the claim-by-claim limitation mapping table
- Each mapping row has a [View ↗] button to open the Source Viewer

**Components to build:**

`RejectionCard.jsx`:
- Collapsed: one-line summary (basis, claims, references, badge)
- Expanded: full claim mapping table + MPEP guidance
- Smooth expand/collapse animation (CSS transition, not spring physics —
  keep it professional)

`ClaimMappingTable.jsx`:
- Three columns: Limitation text | Mapped reference + passage | Verification status
- Monospace font for claim limitation text (patent claims have specific formatting)
- Each row is independently verifiable with its own badge
- [View ↗] opens Source Viewer for that specific passage

`VerificationBadge.jsx`:
- Four states: Verified (green dot + "Verified"), Review (amber dot + "Review Suggested"),
  Unverified (red dot + "Unverified"), N/A (gray dot + "N/A")
- Tooltip on hover explains what the status means:
  - Verified: "This assertion has been confirmed against the original source document."
  - Review: "The source exists but may not fully support this assertion. Manual review recommended."
  - Unverified: "Could not verify this assertion. The source may not exist or may not say what is claimed."
- Keep the component tiny — it appears dozens of times on a single analysis page

**Action buttons at the top:**
- [Draft Response] → navigates to `/analysis/:id/draft`
- [Export Analysis] → downloads .docx with the structured analysis
- [View Raw OA] → opens the original office action text in a modal

**Acceptance criteria:** Rejection cards render correctly for all 5 test applications.
Expand/collapse works. Verification badges display correct status. [View ↗] opens
source viewer. All data comes from the real API, not mock data.

### Task 13: Build the Source Viewer

Slide-out panel that shows source text when [View ↗] is clicked.

**Implementation:**
- Slide in from the right (50% width on desktop, full width on mobile)
- Shows: source document identifier (patent number, MPEP section), specific location
  (column/line, paragraph, figure), the source text with the relevant passage
  highlighted, the examiner's assertion about this source, the verification result
  and explanation, and the user's claim limitation for comparison
- Close on click outside, Escape key, or × button

**This is the trust-building component.** It answers the practitioner's core question:
"Can I see exactly what the AI is basing this on?" If this component works well,
the practitioner trusts the tool. If it's broken or unclear, they don't.

**Acceptance criteria:** Source viewer opens with correct source text for each
[View ↗] click. Relevant passage is highlighted. Verification explanation is shown.
Closes cleanly.

### Task 14: Build the Response Draft editor

Editable response draft with inline verification and source panel.

**Implementation:**
- Strategy selector at top (Argue / Amend / Both) — changing strategy triggers
  a new draft generation via the API
- Rich text editor for the draft body (use Tiptap with a minimal toolbar:
  bold, italic, paragraph, heading, ordered list — no fancy formatting)
- Inline verification badges appear next to sourced claims in the draft text
  (these are read-only annotations overlaid on the editable text)
- Source panel below or beside the editor showing all sources cited in the draft,
  each with its own verification badge and [View ↗] link
- Action buttons: [Export to Word], [Copy Text], [Save Draft]

**Export to Word (.docx):**
- Use the `docx` npm package or a backend endpoint that generates the .docx
- The exported document should be formatted as a standard USPTO office action
  response: centered "REMARKS" heading, body paragraphs with standard font
  (Times New Roman 12pt or similar), footnotes for citations
- Read `docs/trusted-legal-ai-architecture.md` and `/mnt/skills/public/docx/SKILL.md`
  for guidance on .docx generation

**Acceptance criteria:** Draft renders in editable rich text. Strategy selector triggers
new draft. Inline badges display correctly. Export to Word produces a properly formatted
.docx that a patent attorney could file (with appropriate modifications).

### Task 15: Build the Sidebar and recent analyses list

The sidebar provides navigation and quick access to recent work.

**Implementation:**
- Dark background (stone-900)
- Logo/name at top: "ATTICUS" in Merriweather, white, small caps or letter-spaced
- Navigation links: New Analysis, Settings
- "Recent Analyses" section: list of recent analyses sorted by date, showing
  application number (truncated), rejection types as small badges, relative time
  ("2 hours ago", "Yesterday")
- Clicking a recent analysis navigates to `/analysis/:id`
- Fetch recent analyses from `GET /api/v1/analyses?tenant_id=default&limit=20`

**Acceptance criteria:** Sidebar renders with navigation. Recent analyses load from API.
Clicking navigates to the correct analysis. Active page is highlighted in the nav.

### Task 16: API endpoints for frontend

Ensure the backend API supports everything the frontend needs. Verify or add:

```
GET  /api/v1/analyses                    # List recent analyses for tenant
GET  /api/v1/analyses/:id                # Get full analysis with verification
POST /api/v1/analyze                     # Create new analysis (the existing endpoint)
POST /api/v1/analyses/:id/draft          # Generate response draft
GET  /api/v1/analyses/:id/draft          # Get latest draft
PUT  /api/v1/analyses/:id/draft          # Save edited draft
GET  /api/v1/analyses/:id/sources/:ref   # Get source text for a specific reference
GET  /api/v1/analyses/:id/export         # Export analysis as .docx
GET  /api/v1/analyses/:id/draft/export   # Export draft response as .docx
DELETE /api/v1/analyses/:id              # Hard delete (compliance — right to deletion)
GET  /api/v1/health                      # Health check
```

**CORS:** Enable CORS for the frontend origin (localhost:3000 in dev).

**Response format:** All endpoints return JSON with consistent error format:
```json
{
  "error": {
    "code": "APPLICATION_NOT_FOUND",
    "message": "Could not find application 19999999 in the USPTO database.",
    "suggestion": "Please verify the application number and try again."
  }
}
```

Error messages should be user-friendly (the frontend displays them directly).
No stack traces, no technical jargon, no HTTP status codes in the message body.

### Task 17: Wire frontend to real backend data

Remove any mock data or placeholder content from Phase 1 frontend work.
Every component should fetch from the real API.

**API client setup:**

```javascript
// frontend/src/api/client.js
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function analyzeApplication(applicationNumber) {
  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ application_number: applicationNumber }),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.error?.message || 'Analysis failed');
  }
  return res.json();
}

export async function getAnalysis(id) {
  const res = await fetch(`${API_BASE}/api/v1/analyses/${id}`);
  if (!res.ok) throw new Error('Failed to load analysis');
  return res.json();
}

export async function generateDraft(analysisId, strategy) {
  const res = await fetch(`${API_BASE}/api/v1/analyses/${analysisId}/draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategy }),
  });
  if (!res.ok) throw new Error('Draft generation failed');
  return res.json();
}

// ... etc for all endpoints
```

**Loading and error states for every view:**
- Loading: subtle spinner + descriptive text ("Loading analysis...")
- Error: clear message + retry button + suggestion
- Empty: friendly empty state ("No analyses yet. Start by analyzing an office action.")

**Acceptance criteria:** Every view fetches real data from the backend. No mock data remains.
Loading, error, and empty states all work correctly. The full flow works end-to-end:
enter application number → see analysis → expand rejections → view sources →
draft response → export to Word.

---

## PART D: Packaging & distribution — from web app to professional installable application

This part defines the path from "runs on my machine with docker-compose" to "a patent
attorney downloads Atticus.dmg, double-clicks, and it works." Not all of this is built
in Phase 3 — Tasks 18–19 are in scope now; the rest is roadmap with decisions made
early so nothing built today blocks it later.

### Why architecture decisions today matter for packaging tomorrow

Law firms are conservative buyers of software. Many small/boutique patent firms will
NOT adopt a cloud SaaS that ships client work product to someone else's server — but
they WILL install a desktop app that keeps everything local. Conversely, larger firms
with IT departments prefer centrally-managed web deployments. The winning strategy is
to support both from one codebase, which requires deciding now:

1. **The backend must be self-contained and relocatable.** No hardcoded paths,
   no assumptions about Docker, all config via environment variables or a config file.
   (Already mostly true — keep it that way.)
2. **The frontend must not assume a fixed API origin.** API base URL is injected
   at runtime (already done via `VITE_API_URL`).
3. **The database must have an embedded-mode option.** PostgreSQL+pgvector is right
   for server deployments, but a desktop app can't ask a lawyer to run Docker.
   Plan for a SQLite + `sqlite-vec` fallback (see Task 18).

### The three distribution tiers (roadmap)

```
Tier 1 — DEVELOPER (now):        git clone + docker compose up
Tier 2 — SELF-HOSTED SERVER:     Single Docker image, firm IT deploys it
                                 (docker run ghcr.io/you/atticus:latest)
Tier 3 — DESKTOP APP:            Downloadable installer (.dmg / .msi / .AppImage)
                                 Everything runs locally on the attorney's machine
```

**Tier 2** is nearly free to produce once the app works: one multi-stage Dockerfile that
builds the frontend, bundles it into FastAPI's static file serving, and runs everything
in one container against an external Postgres. This is what a firm's IT department wants.

**Tier 3** is the "professional app" experience and the differentiator for solo
practitioners and small firms — and it has a privilege story that sells itself:
*client data never leaves the attorney's laptop except for the LLM API call.*

### Desktop framework decision: Tauri (not Electron)

Use **Tauri v2** when we get to Tier 3, for these reasons:

| | Tauri | Electron |
|---|---|---|
| Installer size | ~10–20 MB | ~150–250 MB |
| Memory footprint | Low (uses OS webview) | High (bundles Chromium) |
| Sidecar process support | First-class (`tauri-plugin-shell`) | Manual |
| Auto-updater | Built-in, signed | Requires electron-updater |
| Security model | Rust core, explicit allowlist | Node in main process |
| Our frontend reuse | 100% — it's the same React build | 100% |

The architecture for the desktop build:

```
┌─────────────────────────────────────────────────┐
│  Atticus.app (Tauri shell)                      │
│  ┌───────────────────┐  ┌────────────────────┐  │
│  │ React frontend    │  │ Python backend as  │  │
│  │ (same build as    │──│ a SIDECAR binary   │  │
│  │  web version)     │  │ (PyInstaller/      │  │
│  │                   │  │  PyOxidizer)       │  │
│  └───────────────────┘  └─────────┬──────────┘  │
│                                   │             │
│                         ┌─────────▼──────────┐  │
│                         │ SQLite +           │  │
│                         │ sqlite-vec         │  │
│                         │ (embedded, local)  │  │
│                         └────────────────────┘  │
└────────────────────────────────┬────────────────┘
                                 │ HTTPS (only external calls)
                     ┌───────────▼───────────┐
                     │ USPTO API + Anthropic │
                     │ API (user's own keys) │
                     └───────────────────────┘
```

The Python backend is compiled to a single binary with PyInstaller, shipped as a Tauri
"sidecar," started on app launch on a random localhost port, and the webview talks to it
exactly like the browser talks to FastAPI today. Nothing about the backend code changes.

### Task 18 (IN SCOPE for Phase 3): Storage abstraction layer

To keep the desktop path open, abstract the vector store and database behind interfaces
now, while the codebase is small:

```python
# src/db/backends.py
from abc import ABC, abstractmethod

class VectorBackend(ABC):
    """Abstract vector storage. Implementations: PgVectorBackend, SqliteVecBackend."""
    @abstractmethod
    def upsert(self, collection: str, chunks: list[Chunk]) -> None: ...
    @abstractmethod
    def search(self, collection: str, embedding: list[float],
               top_k: int, filters: dict | None = None) -> list[SearchResult]: ...
    @abstractmethod
    def count(self, collection: str) -> int: ...

class StorageBackend(ABC):
    """Abstract relational storage. Implementations: PostgresBackend, SqliteBackend."""
    ...
```

Wire the existing pgvector code through `PgVectorBackend`. Do NOT implement the SQLite
backend yet — just ensure nothing outside `src/db/` imports psycopg or writes raw SQL
directly. Config selects the backend:

```
# .env
STORAGE_BACKEND=postgres     # postgres | sqlite (sqlite reserved for desktop build)
```

**Acceptance criteria:** All database access flows through the backend interfaces.
Existing tests pass unchanged. `grep -r "import psycopg" src/ | grep -v "src/db/"`
returns nothing.

### Task 19 (IN SCOPE for Phase 3): Single-image server distribution (Tier 2)

Create the production Dockerfile that packages everything into one deployable image:

```dockerfile
# Dockerfile.production — multi-stage build
# Stage 1: build frontend
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build            # outputs to /build/dist

# Stage 2: runtime
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY src/ ./src/
COPY scripts/ ./scripts/
# Serve the built frontend from FastAPI (StaticFiles mount at /)
COPY --from=frontend /build/dist ./static/
EXPOSE 8000
HEALTHCHECK CMD curl -f http://localhost:8000/api/v1/health || exit 1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Add to `src/main.py`: mount the static frontend when `./static` exists, with SPA
fallback (all non-`/api` routes serve `index.html`). Tag and document:

```bash
docker build -f Dockerfile.production -t atticus:latest .
docker run -p 8000:8000 --env-file .env atticus:latest
# → open http://localhost:8000 — full app, one container
```

**Acceptance criteria:** One `docker run` command serves the complete application
(UI + API) on a single port. Documented in README.

### Roadmap tasks (NOT in Phase 3 — documented so nothing blocks them)

**R1. SQLite + sqlite-vec backend.** Implement `SqliteVecBackend` against the Task 18
interface. Embedding model runs locally already (sentence-transformers), so the desktop
app has zero extra dependencies. Ship the MPEP index pre-built inside the installer
(it's public data — ~655 chunks is a few MB).

**R2. Backend sidecar binary.** PyInstaller spec that bundles the FastAPI app + models
into one executable per platform. Watch for: sentence-transformers model weights
(~90 MB — download on first run to the app data dir instead of bundling), and
tokenizer/torch native libs (use CPU-only torch to keep size sane).

**R3. Tauri shell.** Wrap the existing React build. Sidecar lifecycle: start backend
on launch → health-check poll → load UI; kill child process on quit. Store user data
in platform-standard locations (`~/Library/Application Support/Atticus` on macOS,
`%APPDATA%\Atticus` on Windows, `~/.local/share/atticus` on Linux).

**R4. Code signing & notarization.** Required or the app is effectively undistributable
to lawyers (unsigned apps trigger scary OS warnings — instant credibility killer):
- macOS: Apple Developer ID ($99/yr), `codesign` + `notarytool`. Tauri automates both.
- Windows: Authenticode cert. Prefer an EV or Azure Trusted Signing cert (~$100–400/yr)
  to avoid SmartScreen "unrecognized app" warnings.
- Linux: AppImage with embedded signature (lowest priority — few target users).

**R5. Auto-updates.** Tauri's built-in updater with a signed update manifest hosted on
GitHub Releases. Critical for a legal tool: MPEP revisions, USPTO API changes, and
verification improvements need to reach users without manual reinstalls. Include an
in-app "What's new" note per release — lawyers need to know when analysis behavior changes.

**R6. First-run experience.** Setup wizard on first launch: (1) enter USPTO API key with
a "how to get one" link, (2) enter Anthropic API key with cost explanation and the
option to run deterministic-only mode without one, (3) download embedding model with
progress bar, (4) optional: seed MPEP index (or ship pre-built). A lawyer should go
from download to first analysis in under 5 minutes without reading documentation.

**R7. Crash reporting & diagnostics — privilege-aware.** Standard crash reporters
(Sentry et al.) capture request payloads and breadcrumbs — which here could include
client work product. Rule: crash reports contain stack traces and system info ONLY,
never request/response bodies, never analysis content. Make diagnostics opt-in with
a plain-language explanation, and document this in the data handling policy. This is
a selling point, not a limitation.

**R8. Versioned releases.** Semantic versioning, a CHANGELOG.md, and a GitHub Actions
release workflow: on tag push → run tests → build Docker image (Tier 2) → build
signed installers for macOS/Windows (Tier 3) → attach to GitHub Release. Set this up
once R3/R4 exist.

### Distribution decision summary

| Decision | Choice | When |
|---|---|---|
| Storage abstraction | Interfaces now, SQLite later | Phase 3 (Task 18) |
| Server packaging | Single Docker image | Phase 3 (Task 19) |
| Desktop framework | Tauri v2 + Python sidecar | Roadmap (R2–R3) |
| Desktop database | SQLite + sqlite-vec | Roadmap (R1) |
| Code signing | Apple Developer ID + Authenticode | Roadmap (R4) |
| Updates | Tauri updater + GitHub Releases | Roadmap (R5) |
| Crash reporting | Opt-in, metadata-only, no content | Roadmap (R7) |

---

## End-of-sprint deliverables

**Part A — Legal compliance:**
1. ✅ Database schema updated with data classification (public vs. client tables)
2. ✅ Tenant isolation implemented (tenant_id on all client data)
3. ✅ Publication status check enforced before indexing
4. ✅ Data handling policy documented

**Part B — LLM integration:**
5. ✅ Anthropic API wired up with cost controls and audit logging
6. ✅ LLM-enriched analysis tested on all 5 applications
7. ✅ Verification pipeline tested on LLM outputs with measured hallucination rate
8. ✅ Response drafting tested with verification
9. ✅ Compliance checks added to evaluation harness

**Part C — UI / Web application:**
10. ✅ React app with routing, sidebar layout, and professional design system
11. ✅ New Analysis page (3 input methods, progress feedback, error handling)
12. ✅ Analysis Overview page (rejection cards, claim mapping, verification badges)
13. ✅ Source Viewer (slide-out panel with highlighted source text)
14. ✅ Response Draft editor (rich text, inline badges, strategy selector)
15. ✅ Export to Word (.docx) for both analysis and response drafts
16. ✅ All views wired to real backend data (no mock data)
17. ✅ All tests passing (33 + new compliance + integration + frontend tests)

**Part D — Packaging & distribution:**
18. ✅ Storage abstraction layer (VectorBackend/StorageBackend interfaces; pgvector wired through them)
19. ✅ Single-image server distribution (Dockerfile.production; one `docker run` serves UI + API)

## Budget estimate for this sprint

| Task | Estimated API cost |
|------|-------------------|
| Validate Anthropic key | ~$0.001 |
| 5 full analyses (Sonnet) | ~$2.50–7.50 |
| Verification on 5 analyses (Haiku) | ~$0.50–1.50 |
| 5 response drafts (Sonnet) | ~$2.50–5.00 |
| Iteration/debugging (backend + frontend testing) | ~$3.00–8.00 |
| **Total** | **~$9–22** |

This is well within a $25 initial credit purchase.

---

## What comes after Phase 3

- User authentication (email/password or OAuth) and real multi-tenancy
- Independent ground-truth creation (manual annotation, not parser-derived)
- Broader patent corpus seeding (more TC 2100/2600 patents)
- Mobile-responsive layout refinement
- Keyboard shortcuts for power users (Cmd+E to export, Cmd+N for new analysis)
- SOC 2 readiness checklist (for eventual production deployment)
- Encryption at rest implementation
- Anthropic ZDR agreement for production use
- User onboarding flow (first-time setup wizard for API keys)
- Collaborative features (share analyses within a firm)