"""Anthropic Claude API wrapper.

Centralizes all model access with:
  * model selection (Sonnet for generation, Haiku for verification)
  * retry with exponential backoff on transient errors
  * token + cost accounting
  * structured JSON output parsing (tool-use / JSON mode)

No prompt strings live here — they all come from ``prompt_templates.py``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings

logger = logging.getLogger(__name__)

# Approximate USD per 1M tokens (input, output) — used for cost tracking, not billing.
# Current as of 2026-06; verify at https://platform.claude.com/docs/en/pricing.
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


@dataclass
class Usage:
    """Running token / cost accounting across calls made by one client instance."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0

    def add(self, model: str, in_tok: int, out_tok: int) -> None:
        in_price, out_price = _PRICING.get(model, (0.0, 0.0))
        self.input_tokens += in_tok
        self.output_tokens += out_tok
        self.cost_usd += (in_tok * in_price + out_tok * out_price) / 1_000_000
        self.calls += 1


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict = field(default_factory=dict)


class BudgetExceededError(RuntimeError):
    """Raised when cumulative spend on an LLMClient exceeds ``max_cost_per_run_usd``."""


class LLMClient:
    """Wrapper around the Anthropic SDK with retries and cost tracking."""

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.anthropic_api_key
        self.generation_model = settings.generation_model
        self.verification_model = settings.verification_model
        self.max_cost_per_run_usd = settings.max_cost_per_run_usd
        self.enable_prompt_caching = settings.enable_prompt_caching
        self.usage = Usage()
        self._client = None  # lazily created

    def _check_budget(self) -> None:
        cap = self.max_cost_per_run_usd
        if cap and self.usage.cost_usd >= cap:
            raise BudgetExceededError(
                f"Spend ${self.usage.cost_usd:.4f} reached the per-run cap of ${cap:.4f} "
                f"after {self.usage.calls} call(s). Raise MAX_COST_PER_RUN_USD or start a new run."
            )

    @property
    def client(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
            import anthropic  # deferred import

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    @retry(reraise=True, stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=30))
    def complete(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Single completion. Defaults to the generation model."""
        model = model or self.generation_model
        self._check_budget()  # stop before spending if the cap is already reached
        # Cache the stable system prompt so repeated calls pay ~0.1x on those input tokens.
        system_param: object = system
        if self.enable_prompt_caching and system:
            system_param = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        message = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_param,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in message.content if block.type == "text")
        self.usage.add(model, message.usage.input_tokens, message.usage.output_tokens)
        self._check_budget()  # surface overage immediately after the call that caused it
        return LLMResponse(
            text=text,
            model=model,
            usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> dict:
        """Completion that must return JSON. Robust to fenced code blocks."""
        resp = self.complete(system, user, model=model, max_tokens=max_tokens, temperature=0.0)
        return _extract_json(resp.text)

    def verify(self, system: str, user: str, max_tokens: int = 1024) -> LLMResponse:
        """Completion using the cheaper verification model (Haiku)."""
        return self.complete(
            system, user, model=self.verification_model, max_tokens=max_tokens
        )


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response, tolerating ```json fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1:
        candidate = candidate[start : end + 1]
    return json.loads(candidate)
