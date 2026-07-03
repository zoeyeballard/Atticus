"""Data classification rules for Atticus.

Determines what can be stored where and how. This is the machine-readable form of the policy in
``docs/data-handling-policy.md`` and the schema split in ``src/db/migrations`` — PUBLIC data
(published patents, MPEP) is freely storable and shareable; CLIENT / PRIVILEGED data (analyses,
drafts, attorney work product) is tenant-isolated, retention-limited, and never used for retrieval
or training.
"""

from __future__ import annotations

from enum import Enum

# Fixed default tenant for the single-user prototype (matches 002_compliance.sql).
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


class DataClass(str, Enum):
    PUBLIC = "public"  # Published patents, MPEP, granted patents
    CLIENT = "client"  # Analysis results, drafts, audit trails
    PRIVILEGED = "privileged"  # Attorney work product, strategy decisions


# Storage policy per classification. Keyed by DataClass for easy lookup.
STORAGE_POLICY: dict[DataClass, dict] = {
    DataClass.PUBLIC: {
        "can_persist": True,
        "can_share_across_tenants": True,
        "can_use_for_retrieval": True,
        "encryption_required": False,  # Public data; encrypt if convenient
        "retention_days": None,  # Permanent
        "can_send_to_llm": True,  # Safe to include in prompts
    },
    DataClass.CLIENT: {
        "can_persist": True,
        "can_share_across_tenants": False,  # NEVER cross tenant boundaries
        "can_use_for_retrieval": False,  # Never index client data for other users
        "encryption_required": True,  # Required before production use
        "retention_days": 90,  # Configurable per tenant
        "can_send_to_llm": True,  # Via API with no-training terms only
    },
    DataClass.PRIVILEGED: {
        "can_persist": False,  # Minimize persistence of privileged content
        "can_share_across_tenants": False,
        "can_use_for_retrieval": False,
        "encryption_required": True,
        "retention_days": 30,  # Shorter retention for privileged materials
        "can_send_to_llm": True,  # With extra caution; log the fact, not the content
    },
}

_PUBLIC_SOURCES = {
    "uspto_published_patent",
    "uspto_published_application",
    "uspto_office_action",  # OAs for published applications are public
    "mpep",
    "ptab_decision",
    "patent_classification",
}


def classify_data(source: str) -> DataClass:
    """Classify data by its source. Anything from user interaction is CLIENT data at minimum."""
    if source in _PUBLIC_SOURCES:
        return DataClass.PUBLIC
    return DataClass.CLIENT


def policy_for(source: str) -> dict:
    return STORAGE_POLICY[classify_data(source)]
