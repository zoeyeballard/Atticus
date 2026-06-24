"""Confirm the Anthropic API key works and billing is active — for ~$0.0001.

Usage:
    python scripts/validate_anthropic.py

Makes one tiny Haiku call and reports the model, token usage, and cost. A 400
"credit balance is too low" means the key is valid but the account has no API
credits yet (the claude.ai subscription is separate — add credits at
https://console.anthropic.com → Plans & Billing).
"""

from __future__ import annotations

import sys

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from src.config import get_settings
from src.generation.llm_client import LLMClient


def main() -> int:
    if not get_settings().anthropic_configured:
        print("ANTHROPIC_API_KEY is not set in .env.")  # noqa: T201
        return 1
    client = LLMClient()
    try:
        resp = client.verify("You are a connectivity test.", "Reply with exactly: OK", max_tokens=10)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        print(f"FAILED: {type(exc).__name__}: {msg[:300]}")  # noqa: T201
        if "credit balance" in msg.lower():
            print(  # noqa: T201
                "\nThe key is valid but the API account has no credits. The claude.ai plan does "
                "not fund the API — add credits at https://console.anthropic.com (Plans & Billing)."
            )
        elif "authentication" in msg.lower() or "401" in msg:
            print("\nThe key was rejected — check ANTHROPIC_API_KEY in .env.")  # noqa: T201
        return 2
    print(f"OK — model={resp.model}, reply={resp.text.strip()!r}")  # noqa: T201
    print(  # noqa: T201
        f"tokens in/out = {client.usage.input_tokens}/{client.usage.output_tokens}, "
        f"cost = ${client.usage.cost_usd:.6f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
