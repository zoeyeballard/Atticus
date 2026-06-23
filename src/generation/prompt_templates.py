"""All prompts, versioned, in one place.

Rules (per CLAUDE.md):
  * System prompts set the closed-loop constraint boundary — only use provided context, never
    supplement with training knowledge.
  * User prompts carry the full retrieved context, clearly delineated with XML-ish tags.
  * Output is always structured (JSON matching a Pydantic schema).
  * Every prompt is versioned. When a prompt changes, bump its version and keep the history so
    evaluation results stay attributable to a specific prompt version.
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------------------------
# Shared system constraint — the closed-loop boundary every generation prompt inherits.
# --------------------------------------------------------------------------------------------

GROUNDED_SYSTEM_PROMPT = """You are a patent prosecution assistant for USPTO Technology Centers \
2100/2600 (computer architecture and embedded systems). You MUST follow these rules without \
exception:

1. Every factual claim you make must reference a specific document provided in the context.
2. Use the format [Source: document_id, location] for every factual assertion.
3. If the provided context does not contain information needed to answer, respond with \
"INSUFFICIENT_CONTEXT: [what's missing]" — do NOT fill in from your own knowledge.
4. Never invent patent numbers, case names, or MPEP section numbers. If a number is not in the \
provided context, you may not state it.
5. When analyzing claim limitations, quote the exact text from the patent claims and cited \
references. Do not paraphrase quotations.
6. You are drafting for review by a licensed practitioner. Surface uncertainty explicitly rather \
than presenting a guess as a fact.
"""


@dataclass(frozen=True)
class Prompt:
    """A versioned prompt template."""

    name: str
    version: str
    system: str
    template: str  # user-message template with {placeholders}

    def render(self, **kwargs: object) -> str:
        return self.template.format(**kwargs)


# --------------------------------------------------------------------------------------------
# ANALYZE_OFFICE_ACTION — parse an OA into structured analysis.
# --------------------------------------------------------------------------------------------

ANALYZE_OFFICE_ACTION = Prompt(
    name="analyze_office_action",
    version="v1",
    system=GROUNDED_SYSTEM_PROMPT,
    template="""<office_action>
{office_action_text}
</office_action>

<known_references>
{known_references}
</known_references>

<task>
Analyze this office action. Produce a JSON object matching this schema exactly:
{{
  "rejection_type": "non-final" | "final" | "advisory",
  "examiner_name": string | null,
  "art_unit": string | null,
  "mailing_date": string,
  "rejections": [
    {{
      "claim_number": int,
      "rejection_basis": "101" | "102" | "103" | "112(a)" | "112(b)" | "dp",
      "is_independent": bool,
      "limitation_mappings": [
        {{
          "limitation_text": string,        // exact quote from the claim
          "mapped_to_reference": string,    // MUST be one of <known_references>
          "reference_passage": string,      // e.g. "col. 4, lines 23-45"
          "examiner_reasoning": string | null,
          "source_span": string | null      // exact span in the OA supporting this mapping
        }}
      ],
      "cited_references": [
        {{"patent_number": string, "relevant_passages": [string]}}
      ]
    }}
  ],
  "objections": [string],
  "requirements": [string]
}}

You may only list a reference in "mapped_to_reference"/"cited_references" if it appears in
<known_references>. If the OA cites a reference not in that list, add it to "objections" with a
note that it could not be verified. Return ONLY the JSON object.
</task>""",
)


# --------------------------------------------------------------------------------------------
# MAP_CLAIM_LIMITATIONS — map an examiner's rejection to specific claim limitations.
# --------------------------------------------------------------------------------------------

MAP_CLAIM_LIMITATIONS = Prompt(
    name="map_claim_limitations",
    version="v1",
    system=GROUNDED_SYSTEM_PROMPT,
    template="""<claim number="{claim_number}">
{claim_text}
</claim>

<rejection>
{rejection_text}
</rejection>

{reference_blocks}

<task>
For each limitation of claim {claim_number}, identify which reference the examiner maps it to and
the exact passage cited. Quote the limitation text verbatim from the claim. Return a JSON array of
limitation_mapping objects. If the examiner did not map a limitation, set "mapped_to_reference" to
null and explain in "examiner_reasoning".
</task>""",
)


# --------------------------------------------------------------------------------------------
# IDENTIFY_DISTINCTIONS — technical distinctions vs. cited prior art.
# --------------------------------------------------------------------------------------------

IDENTIFY_DISTINCTIONS = Prompt(
    name="identify_distinctions",
    version="v1",
    system=GROUNDED_SYSTEM_PROMPT,
    template="""<claim number="{claim_number}">
{claim_text}
</claim>

{reference_blocks}

<task>
Identify technical distinctions between the claimed invention and the cited reference(s). For each
distinction, quote the claim limitation and the most relevant reference passage, then state the
difference. Base every statement ONLY on the provided text. Return a JSON array:
[{{"limitation": string, "reference_passage": string, "distinction": string, "source": string}}]
</task>""",
)


# --------------------------------------------------------------------------------------------
# DRAFT_RESPONSE_ARGUMENT — argue a rejection should be overcome.
# --------------------------------------------------------------------------------------------

DRAFT_RESPONSE_ARGUMENT = Prompt(
    name="draft_response_argument",
    version="v1",
    system=GROUNDED_SYSTEM_PROMPT,
    template="""<claim number="{claim_number}">
{claim_text}
</claim>

<rejection basis="{rejection_basis}">
{rejection_text}
</rejection>

{reference_blocks}

{mpep_blocks}

<task>
Draft an argument for why the §{rejection_basis} rejection of claim {claim_number} should be
overcome. Ground every assertion in the provided claim text, reference passages, and MPEP
guidance, using [Source: document_id, location] inline. Do not introduce facts or authorities not
present above. Return JSON:
{{"argument_text": string, "supporting_sources": [string], "confidence": float}}
</task>""",
)


# --------------------------------------------------------------------------------------------
# SUGGEST_AMENDMENTS — propose claim amendments distinguishing over the art.
# --------------------------------------------------------------------------------------------

SUGGEST_AMENDMENTS = Prompt(
    name="suggest_amendments",
    version="v1",
    system=GROUNDED_SYSTEM_PROMPT,
    template="""<claim number="{claim_number}">
{claim_text}
</claim>

<specification_support>
{specification_support}
</specification_support>

{reference_blocks}

<task>
Suggest an amendment to claim {claim_number} that distinguishes over the cited reference(s). The
amendment MUST have written-description support in <specification_support> — quote the supporting
passage. Do not add new matter. Return JSON:
{{"suggested_amendment": string, "specification_support": string, "distinction": string,
  "source": string, "confidence": float}}
</task>""",
)


# --------------------------------------------------------------------------------------------
# Verification prompts (run on the cheaper Haiku model).
# --------------------------------------------------------------------------------------------

DECOMPOSE_CLAIMS = Prompt(
    name="decompose_claims",
    version="v1",
    system="""You decompose AI-generated text into atomic, independently verifiable claims. \
Output only what is asserted; do not add, infer, or correct.""",
    template="""<text>
{text}
</text>

<task>
Break the text into atomic claims. Classify each as one of: "citation", "patent_reference",
"legal_proposition", "factual_assertion", "procedural_claim", "opinion". Return a JSON array:
[{{"claim_text": string, "claim_type": string}}]
</task>""",
)


ENTAILMENT_CHECK = Prompt(
    name="entailment_check",
    version="v1",
    system="""You are a strict natural-language-inference judge. You determine only whether a \
source text supports a claim. You never use outside knowledge.""",
    template="""Given the following source text and claim, determine if the source SUPPORTS,
CONTRADICTS, or is NEUTRAL toward the claim.

Source: {source_text}
Claim: {claim_text}

Respond with JSON: {{"verdict": "ENTAILS" | "CONTRADICTS" | "NEUTRAL", "explanation": string}}""",
)


# Registry for versioned lookup / iteration during evaluation.
ALL_PROMPTS: dict[str, Prompt] = {
    p.name: p
    for p in (
        ANALYZE_OFFICE_ACTION,
        MAP_CLAIM_LIMITATIONS,
        IDENTIFY_DISTINCTIONS,
        DRAFT_RESPONSE_ARGUMENT,
        SUGGEST_AMENDMENTS,
        DECOMPOSE_CLAIMS,
        ENTAILMENT_CHECK,
    )
}
