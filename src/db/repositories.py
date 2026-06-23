"""Data-access layer for analyses, drafts, and the audit trail.

For the prototype we keep an in-memory repository (sufficient for a single-user demo) behind an
interface that a Postgres-backed implementation can later satisfy. Swap ``InMemoryRepository`` for
a ``PostgresRepository`` without touching the API layer.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from src.models.schemas import OfficeActionAnalysis, ResponseDraft


class AuditEvent(dict):
    """A single audit-trail entry (retrieved / generated / verified / flagged)."""


class Repository(Protocol):
    def save_analysis(self, analysis: OfficeActionAnalysis) -> str: ...
    def get_analysis(self, analysis_id: str) -> OfficeActionAnalysis | None: ...
    def save_draft(self, draft: ResponseDraft) -> str: ...
    def append_audit(self, analysis_id: str, event: AuditEvent) -> None: ...
    def get_audit_trail(self, analysis_id: str) -> list[AuditEvent]: ...


class InMemoryRepository:
    """Process-local repository for the prototype."""

    def __init__(self) -> None:
        self._analyses: dict[str, OfficeActionAnalysis] = {}
        self._drafts: dict[str, ResponseDraft] = {}
        self._audit: dict[str, list[AuditEvent]] = {}

    def _new_id(self) -> str:
        return uuid.uuid4().hex

    def save_analysis(self, analysis: OfficeActionAnalysis) -> str:
        analysis_id = self._new_id()
        self._analyses[analysis_id] = analysis
        self._audit.setdefault(analysis_id, [])
        return analysis_id

    def get_analysis(self, analysis_id: str) -> OfficeActionAnalysis | None:
        return self._analyses.get(analysis_id)

    def save_draft(self, draft: ResponseDraft) -> str:
        draft_id = self._new_id()
        self._drafts[draft_id] = draft
        return draft_id

    def append_audit(self, analysis_id: str, event: AuditEvent) -> None:
        self._audit.setdefault(analysis_id, []).append(event)

    def get_audit_trail(self, analysis_id: str) -> list[AuditEvent]:
        return self._audit.get(analysis_id, [])


# Module-level singleton used by the API for the prototype.
_repository: Repository = InMemoryRepository()


def get_repository() -> Repository:
    return _repository
