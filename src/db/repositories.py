"""Data-access layer for analyses, drafts, and the audit trail.

Tenant-isolated by construction: every client-data method takes a ``tenant_id`` (defaulting to
the prototype's single tenant) and never returns rows from another tenant. For the prototype we
keep an in-memory implementation behind a ``Repository`` protocol; a Postgres-backed one can be
dropped in later without touching the API layer.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from src.config.data_classification import DEFAULT_TENANT_ID
from src.models.schemas import OfficeActionAnalysis, ResponseDraft


class AuditEvent(dict):
    """A single audit-trail entry (retrieved / generated / verified / flagged / llm_api_call)."""


def llm_audit_event(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    purpose: str,
) -> "AuditEvent":
    """Build a metadata-only audit event for an LLM call.

    Records the model, token counts, cost, and purpose — **never** the raw prompt or response,
    which may contain client-privileged content (see docs/data-handling-policy.md).
    """
    return AuditEvent(
        step="llm_api_call",
        event_type="llm_api_call",
        llm_model=model,
        token_count={"input": input_tokens, "output": output_tokens, "cost_usd": round(cost_usd, 6)},
        payload={"purpose": purpose},  # purpose only — no prompt/response content
    )


class StoredAnalysis:
    """An analysis plus its tenant + compliance metadata."""

    def __init__(
        self,
        analysis: OfficeActionAnalysis,
        tenant_id: str,
        publication_verified: bool,
    ) -> None:
        self.analysis = analysis
        self.tenant_id = tenant_id
        self.publication_verified = publication_verified


class Repository(Protocol):
    def save_analysis(
        self, analysis: OfficeActionAnalysis, tenant_id: str = ..., publication_verified: bool = ...
    ) -> str: ...
    def get_analysis(self, analysis_id: str, tenant_id: str = ...) -> OfficeActionAnalysis | None: ...
    def list_analyses(self, tenant_id: str = ..., limit: int = ...) -> list[dict]: ...
    def delete_analysis(self, analysis_id: str, tenant_id: str = ...) -> bool: ...
    def save_draft(self, draft: ResponseDraft, tenant_id: str = ...) -> str: ...
    def get_draft(self, analysis_id: str, tenant_id: str = ...) -> ResponseDraft | None: ...
    def append_audit(self, analysis_id: str, event: AuditEvent, tenant_id: str = ...) -> None: ...
    def get_audit_trail(self, analysis_id: str, tenant_id: str = ...) -> list[AuditEvent]: ...


class InMemoryRepository:
    """Process-local, tenant-aware repository for the prototype."""

    def __init__(self) -> None:
        self._analyses: dict[str, StoredAnalysis] = {}
        self._drafts: dict[str, ResponseDraft] = {}  # keyed by analysis_id (latest draft)
        self._audit: dict[str, list[AuditEvent]] = {}
        self._created: dict[str, str] = {}  # analysis_id -> iso timestamp (set by caller)

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    def _owned(self, analysis_id: str, tenant_id: str) -> bool:
        rec = self._analyses.get(analysis_id)
        return rec is not None and rec.tenant_id == tenant_id

    # -- analyses ----------------------------------------------------------------------------

    def save_analysis(
        self,
        analysis: OfficeActionAnalysis,
        tenant_id: str = DEFAULT_TENANT_ID,
        publication_verified: bool = False,
    ) -> str:
        analysis_id = self._new_id()
        self._analyses[analysis_id] = StoredAnalysis(analysis, tenant_id, publication_verified)
        self._audit.setdefault(analysis_id, [])
        return analysis_id

    def get_analysis(
        self, analysis_id: str, tenant_id: str = DEFAULT_TENANT_ID
    ) -> OfficeActionAnalysis | None:
        rec = self._analyses.get(analysis_id)
        return rec.analysis if rec and rec.tenant_id == tenant_id else None

    def list_analyses(self, tenant_id: str = DEFAULT_TENANT_ID, limit: int = 20) -> list[dict]:
        items = [
            {
                "analysis_id": aid,
                "application_number": rec.analysis.application_number,
                "rejection_type": rec.analysis.rejection_type,
                "rejection_bases": sorted(
                    {r.rejection_basis.value for r in rec.analysis.rejections}
                ),
                "publication_verified": rec.publication_verified,
            }
            for aid, rec in self._analyses.items()
            if rec.tenant_id == tenant_id
        ]
        return items[-limit:][::-1]

    def delete_analysis(self, analysis_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> bool:
        """Hard delete (compliance — right to deletion): purge analysis, draft, and audit."""
        if not self._owned(analysis_id, tenant_id):
            return False
        self._analyses.pop(analysis_id, None)
        self._drafts.pop(analysis_id, None)
        self._audit.pop(analysis_id, None)
        return True

    # -- drafts ------------------------------------------------------------------------------

    def save_draft(self, draft: ResponseDraft, tenant_id: str = DEFAULT_TENANT_ID) -> str:
        # Drafts are keyed by their analysis so the latest draft is retrievable.
        self._drafts[draft.analysis_id] = draft
        return draft.analysis_id

    def get_draft(
        self, analysis_id: str, tenant_id: str = DEFAULT_TENANT_ID
    ) -> ResponseDraft | None:
        if not self._owned(analysis_id, tenant_id):
            return None
        return self._drafts.get(analysis_id)

    # -- audit -------------------------------------------------------------------------------

    def append_audit(
        self, analysis_id: str, event: AuditEvent, tenant_id: str = DEFAULT_TENANT_ID
    ) -> None:
        event.setdefault("tenant_id", tenant_id)
        self._audit.setdefault(analysis_id, []).append(event)

    def get_audit_trail(
        self, analysis_id: str, tenant_id: str = DEFAULT_TENANT_ID
    ) -> list[AuditEvent]:
        if not self._owned(analysis_id, tenant_id):
            return []
        return self._audit.get(analysis_id, [])


# Module-level singleton used by the API for the prototype.
_repository: Repository = InMemoryRepository()


def get_repository() -> Repository:
    return _repository
