"""Tests for budget tracking and the per-run cost cap."""

import pytest

from src.generation.llm_client import BudgetExceededError, LLMClient, Usage


def test_usage_cost_accumulates():
    u = Usage()
    u.add("claude-haiku-4-5", 1_000_000, 1_000_000)  # $1 in + $5 out
    assert round(u.cost_usd, 2) == 6.00
    assert u.calls == 1


def test_budget_cap_trips():
    client = LLMClient(api_key="x")  # no network calls in this test
    client.max_cost_per_run_usd = 0.50
    # Simulate spend beyond the cap, then confirm the guard raises.
    client.usage.add("claude-sonnet-4-6", 200_000, 0)  # $0.60 > $0.50 cap
    with pytest.raises(BudgetExceededError):
        client._check_budget()


def test_budget_cap_disabled_by_default():
    client = LLMClient(api_key="x")
    client.max_cost_per_run_usd = 0.0
    client.usage.add("claude-sonnet-4-6", 10_000_000, 10_000_000)
    client._check_budget()  # no cap → no raise
