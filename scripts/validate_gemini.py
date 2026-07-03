"""Confirm the Gemini API key works — one tiny call (free tier).

Usage: python scripts/validate_gemini.py
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from src.config import get_settings
from src.generation.llm_client import LLMClient


def main() -> int:
    s = get_settings()
    if not s.gemini_configured:
        print("GEMINI_API_KEY is not set in .env.")  # noqa: T201
        return 1
    # Force the Gemini provider for this check regardless of LLM_PROVIDER.
    client = LLMClient()
    client.provider = "gemini"
    client.generation_model = s.gemini_generation_model
    client.verification_model = s.gemini_verification_model
    client._api_key = s.gemini_api_key
    client._client = None
    try:
        resp = client.verify("You are a connectivity test.", "Reply with exactly: OK")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {str(exc)[:300]}")  # noqa: T201
        return 2
    print(f"OK — model={resp.model}, reply={resp.text.strip()!r}")  # noqa: T201
    print(  # noqa: T201
        f"tokens in/out = {client.usage.input_tokens}/{client.usage.output_tokens}, "
        f"cost = ${client.usage.cost_usd:.6f}"
    )
    return 0


if __name__ == "__main__":
    _sys.exit(main())
