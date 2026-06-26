"""Canonical Pydantic schemas for Atticus.

These mirror the data models specified in CLAUDE.md and are the single source of truth. The
domain-specific modules (``patent.py``, ``office_action.py``, ``rejection.py``,
``response_draft.py``) re-export from here so imports read naturally while the definitions stay
in one place.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------------------------
# Office action analysis
# --------------------------------------------------------------------------------------------


class RejectionBasis(str, Enum):
    """Statutory basis for a rejection."""

    SEC_101 = "101"  # Subject matter eligibility
    SEC_102 = "102"  # Novelty (anticipation)
    SEC_103 = "103"  # Obviousness
    SEC_112_A = "112(a)"  # Written description / enablement
    SEC_112_B = "112(b)"  # Definiteness
    DOUBLE_PATENTING = "dp"  # Double patenting


class CitedReference(BaseModel):
    """A prior-art reference cited by the examiner."""

    patent_number: str  # e.g., "US10,234,567"
    publication_number: str | None = None  # e.g., "US2020/0123456"
    first_named_inventor: str = ""
    title: str | None = None
    relevant_passages: list[str] = Field(default_factory=list)  # ["col. 4, lines 23-45", "Fig. 3"]
    verified: bool = False  # Set by citation_verifier
    verification_details: str | None = None


class LimitationMapping(BaseModel):
    """Maps a single claim limitation to where the examiner found it in a reference."""

    limitation_text: str  # The claim limitation text
    mapped_to_reference: str  # Which reference the examiner maps it to
    reference_passage: str  # Where in the reference
    examiner_reasoning: str | None = None  # The examiner's explanation
    source_span: str | None = None  # Exact span in OA that supports this mapping


class ClaimRejection(BaseModel):
    """A rejection of one claim under one statutory basis."""

    claim_number: int
    rejection_basis: RejectionBasis
    is_independent: bool
    limitation_mappings: list[LimitationMapping] = Field(default_factory=list)
    cited_references: list[CitedReference] = Field(default_factory=list)


class OfficeActionAnalysis(BaseModel):
    """Structured analysis of a single office action."""

    application_number: str
    filing_date: str | None = None
    examiner_name: str | None = None
    art_unit: str | None = None
    mailing_date: str = ""
    rejection_type: str = ""  # "non-final", "final", "advisory"
    rejections: list[ClaimRejection] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)  # Claim objections (not rejections)
    requirements: list[str] = Field(default_factory=list)  # Restriction / election requirements
    raw_text: str = ""  # The original OA text for reference
    confidence_score: float = 0.0  # 0-1 overall confidence in the analysis
    unverified_claims: list[str] = Field(default_factory=list)  # Claims that couldn't be verified


# --------------------------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------------------------


class VerificationStatus(str, Enum):
    """Outcome of verifying a single atomic claim against its source."""

    VERIFIED = "verified"  # Claim confirmed against source
    PARTIALLY_SUPPORTED = "partial"  # Source exists but doesn't fully support claim
    UNSUPPORTED = "unsupported"  # Source doesn't support the claim
    FABRICATED = "fabricated"  # Cited source doesn't exist
    UNVERIFIABLE = "unverifiable"  # Cannot be checked (e.g., subjective judgment)


class VerifiedClaim(BaseModel):
    """The verification result for one atomic claim extracted from an AI output."""

    claim_text: str  # The atomic claim from the AI output
    claim_type: str  # "citation", "legal_proposition", "factual", "procedural", "opinion"
    status: VerificationStatus
    source_document: str | None = None  # Document ID that was checked
    source_span: str | None = None  # Exact text span in source
    confidence: float = 0.0  # 0-1
    explanation: str = ""  # Why this verification status was assigned


class VerificationReport(BaseModel):
    """Aggregate verification result for an entire AI output."""

    total_claims: int = 0
    verified_count: int = 0
    partial_count: int = 0
    unsupported_count: int = 0
    fabricated_count: int = 0
    unverifiable_count: int = 0
    overall_confidence: float = 0.0
    claims: list[VerifiedClaim] = Field(default_factory=list)
    needs_human_review: bool = False  # True if any claim is unsupported/fabricated
    review_flags: list[str] = Field(default_factory=list)  # Specific items flagged for attention


# --------------------------------------------------------------------------------------------
# Patents
# --------------------------------------------------------------------------------------------


class PatentClaim(BaseModel):
    """A single patent claim."""

    number: int
    text: str
    is_independent: bool
    depends_on: int | None = None  # Parent claim number for dependent claims


class Patent(BaseModel):
    """A patent / published application with parsed structure."""

    patent_number: str
    publication_number: str | None = None
    title: str | None = None
    first_named_inventor: str = ""
    abstract: str | None = None
    claims: list[PatentClaim] = Field(default_factory=list)
    specification: str | None = None
    classification_codes: list[str] = Field(default_factory=list)
    figures: list[str] = Field(default_factory=list)  # Figure identifiers / captions


class PriorArtSearchResult(BaseModel):
    """A single retrieval hit for prior-art / MPEP search."""

    patent_number: str
    title: str | None = None
    relevance_score: float
    matched_chunk: str
    document_type: str = "patent"  # "patent" | "mpep"
    metadata: dict = Field(default_factory=dict)

    # Convenience aliases so callers can use natural names regardless of document type.
    @property
    def score(self) -> float:
        return self.relevance_score

    @property
    def text(self) -> str:
        return self.matched_chunk

    @property
    def section(self) -> str:
        """MPEP section number (for mpep hits) — falls back to the identifier."""
        return self.metadata.get("section", self.patent_number)

    @property
    def section_type(self) -> str | None:
        """Patent section label (background/summary/claims/…) for patent hits."""
        return self.metadata.get("section_type")


# --------------------------------------------------------------------------------------------
# Response drafting
# --------------------------------------------------------------------------------------------


class ResponseArgument(BaseModel):
    """A single argument paragraph in a response draft, with its supporting source."""

    claim_number: int
    rejection_basis: RejectionBasis
    strategy: str  # "argue" | "amend"
    argument_text: str
    supporting_sources: list[str] = Field(default_factory=list)  # [Source: id, location]
    suggested_amendment: str | None = None
    confidence: float = 0.0


class ResponseDraft(BaseModel):
    """A full office-action response draft, per-claim, with verification."""

    analysis_id: str
    application_number: str
    strategy: str  # "argue" | "amend" | "both"
    arguments: list[ResponseArgument] = Field(default_factory=list)
    verification: VerificationReport | None = None
