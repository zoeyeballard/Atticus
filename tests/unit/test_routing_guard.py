"""Classification-aware LLM routing guard (Phase 4 Task 2).

It must be structurally impossible for CLIENT/PRIVILEGED data to reach a training-enabled
provider tier.
"""

import pytest

from src.config.data_classification import DataClass
from src.generation.llm_client import DataClassificationError, LLMClient


def _client(provider: str, tier: str) -> LLMClient:
    c = LLMClient(api_key="x")
    c.provider = provider
    c.tier = tier
    return c


def test_client_data_blocked_on_gemini_free():
    with pytest.raises(DataClassificationError):
        _client("gemini", "free")._check_data_class(DataClass.CLIENT)


def test_privileged_data_blocked_on_gemini_free():
    with pytest.raises(DataClassificationError):
        _client("gemini", "free")._check_data_class(DataClass.PRIVILEGED)


def test_public_data_allowed_on_gemini_free():
    _client("gemini", "free")._check_data_class(DataClass.PUBLIC)  # no raise


def test_client_data_allowed_on_anthropic_api():
    _client("anthropic", "api")._check_data_class(DataClass.CLIENT)  # no raise


def test_client_data_allowed_on_gemini_paid():
    _client("gemini", "paid")._check_data_class(DataClass.CLIENT)  # no raise


def test_unknown_tier_fails_closed():
    # An unregistered (provider, tier) is treated as training-enabled → blocks client data.
    with pytest.raises(DataClassificationError):
        _client("gemini", "totally-unknown")._check_data_class(DataClass.CLIENT)
