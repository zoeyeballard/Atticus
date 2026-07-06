"""LLM API wrapper — provider-agnostic.

Centralizes all model access behind one interface (``complete`` / ``complete_json`` / ``verify``)
so the rest of the codebase never touches a provider SDK directly:
  * provider selection (Anthropic Claude or Google Gemini) via ``LLM_PROVIDER``
  * model selection (a stronger model for generation, a cheaper one for verification)
  * retry with exponential backoff
  * token + cost accounting and a per-run budget cap
  * structured JSON output

No prompt strings live here — they all come from ``prompt_templates.py``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.config.data_classification import DataClass

logger = logging.getLogger(__name__)

# Whether a (provider, tier) may train on / retain inputs. Extend as providers/tiers are added.
# Unknown combinations are treated as training-enabled (fail closed).
PROVIDER_CAPABILITIES: dict[tuple[str, str], dict] = {
    ("gemini", "free"): {"trains_on_inputs": True},
    ("gemini", "paid"): {"trains_on_inputs": False},
    ("anthropic", "api"): {"trains_on_inputs": False},
    ("anthropic", "free"): {"trains_on_inputs": False},  # Anthropic API never trains by default
    ("vertex", "enterprise"): {"trains_on_inputs": False},
}


class DataClassificationError(RuntimeError):
    """Raised when client/privileged data would be routed to a training-enabled provider tier."""

# Approximate USD per 1M tokens (input, output) — for cost tracking, not billing.
# Gemini has a free tier (effective $0 within quota); list rates are for accounting.
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
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
    """Provider-agnostic LLM wrapper with retries, cost tracking, and a budget cap."""

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.provider = settings.llm_provider
        if self.provider == "gemini":
            self._api_key = api_key if api_key is not None else settings.gemini_api_key
            self.generation_model = settings.gemini_generation_model
            self.verification_model = settings.gemini_verification_model
        else:
            self._api_key = api_key if api_key is not None else settings.anthropic_api_key
            self.generation_model = settings.generation_model
            self.verification_model = settings.verification_model
        self.tier = settings.llm_tier
        self.max_cost_per_run_usd = settings.max_cost_per_run_usd
        self.enable_prompt_caching = settings.enable_prompt_caching
        self.usage = Usage()
        self._client = None  # lazily created, provider-specific

    def _check_data_class(self, data_class: DataClass) -> None:
        """Refuse to send client/privileged data to a provider tier that may train on inputs."""
        if data_class == DataClass.PUBLIC:
            return
        caps = PROVIDER_CAPABILITIES.get((self.provider, self.tier), {"trains_on_inputs": True})
        if caps["trains_on_inputs"]:
            raise DataClassificationError(
                f"Cannot send {data_class.value} data to {self.provider}/{self.tier}: this "
                "provider tier may train on inputs, which risks destroying attorney-client "
                "privilege (see docs/data-handling-policy.md and U.S. v. Heppner). Configure a "
                "no-training provider: LLM_PROVIDER=anthropic, or LLM_PROVIDER=gemini with "
                "LLM_TIER=paid."
            )

    def _check_budget(self) -> None:
        cap = self.max_cost_per_run_usd
        if cap and self.usage.cost_usd >= cap:
            raise BudgetExceededError(
                f"Spend ${self.usage.cost_usd:.4f} reached the per-run cap of ${cap:.4f} "
                f"after {self.usage.calls} call(s). Raise MAX_COST_PER_RUN_USD or start a new run."
            )

    # -- client construction -----------------------------------------------------------------

    @property
    def client(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(f"No API key configured for provider '{self.provider}'.")
            if self.provider == "gemini":
                from google import genai  # deferred import

                self._client = genai.Client(api_key=self._api_key)
            else:
                import anthropic  # deferred import

                self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    # -- unified completion ------------------------------------------------------------------

    def complete(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        json_mode: bool = False,
        data_class: DataClass = DataClass.CLIENT,
    ) -> LLMResponse:
        """Single completion. Defaults to the generation model. Dispatches by provider.

        ``data_class`` defaults to CLIENT (conservative): callers working on public data must pass
        ``DataClass.PUBLIC`` explicitly. The compliance and budget guards run before any network
        call and are *not* retried; only the provider request is retried (with enough backoff to
        cross a free-tier per-minute rate-limit window).
        """
        self._check_data_class(data_class)
        model = model or self.generation_model
        self._check_budget()
        resp = self._dispatch(system, user, model, max_tokens, temperature, json_mode)
        self._check_budget()
        return resp

    # Retry the network call itself — long enough to cross a ~60s RPM window on the free tier.
    @retry(reraise=True, stop=stop_after_attempt(6), wait=wait_exponential(min=2, max=60))
    def _dispatch(self, system, user, model, max_tokens, temperature, json_mode) -> LLMResponse:
        if self.provider == "gemini":
            return self._complete_gemini(system, user, model, max_tokens, temperature, json_mode)
        return self._complete_anthropic(system, user, model, max_tokens, temperature)

    def _complete_anthropic(self, system, user, model, max_tokens, temperature) -> LLMResponse:
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
        text = "".join(b.text for b in message.content if b.type == "text")
        self.usage.add(model, message.usage.input_tokens, message.usage.output_tokens)
        return LLMResponse(
            text=text,
            model=model,
            usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )

    def _complete_gemini(self, system, user, model, max_tokens, temperature, json_mode) -> LLMResponse:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_mode else None,
            # Disable "thinking" — we want deterministic structured extraction, and thinking
            # tokens otherwise consume the output budget and truncate the JSON response.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        resp = self.client.models.generate_content(model=model, contents=user, config=config)
        um = resp.usage_metadata
        in_tok = getattr(um, "prompt_token_count", 0) or 0
        out_tok = getattr(um, "candidates_token_count", 0) or 0
        self.usage.add(model, in_tok, out_tok)
        return LLMResponse(
            text=resp.text or "",
            model=model,
            usage={"input_tokens": in_tok, "output_tokens": out_tok},
        )

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        max_tokens: int = 4096,
        data_class: DataClass = DataClass.CLIENT,
    ) -> dict:
        """Completion that must return JSON. Uses native JSON mode on Gemini; robust parsing else."""
        resp = self.complete(
            system, user, model=model, max_tokens=max_tokens, temperature=0.0,
            json_mode=(self.provider == "gemini"), data_class=data_class,
        )
        return _extract_json(resp.text)

    def verify(
        self, system: str, user: str, max_tokens: int = 1024,
        data_class: DataClass = DataClass.CLIENT,
    ) -> LLMResponse:
        """Completion using the cheaper verification model."""
        return self.complete(
            system, user, model=self.verification_model, max_tokens=max_tokens,
            data_class=data_class,
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
