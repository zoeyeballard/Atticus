"""Compare two draft-eval JSON reports side by side.

Usage:
    python scripts/compare_evaluations.py A.json B.json

Prints a side-by-side table of verified rate, review rate, hallucination rate, and usage —
useful for provider/model comparisons (e.g. Anthropic vs. Gemini, or flash vs. flash-lite) on the
same test set. Works on any two `draft_eval_*.json` files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _label(report: dict) -> str:
    return f"{report.get('provider', '?')}/{report.get('generation_model', '?')}"


def _row(name: str, a, b) -> str:
    return f"  {name:<20} {a:>18} {b:>18}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare two draft-eval reports.")
    ap.add_argument("a")
    ap.add_argument("b")
    args = ap.parse_args()

    ra = json.loads(Path(args.a).read_text())
    rb = json.loads(Path(args.b).read_text())
    aa, ab = ra.get("aggregate", {}), rb.get("aggregate", {})

    print(_row("metric", _label(ra), _label(rb)))  # noqa: T201
    print("  " + "-" * 56)  # noqa: T201
    for key, fmt in (("verified_rate", "{:.1%}"), ("review_rate", "{:.1%}"),
                     ("hallucination_rate", "{:.1%}")):
        va = fmt.format(aa.get(key, 0)) if key in aa else "—"
        vb = fmt.format(ab.get(key, 0)) if key in ab else "—"
        print(_row(key, va, vb))  # noqa: T201
    ua, ub = aa.get("usage", {}), ab.get("usage", {})
    print(_row("calls", ua.get("calls", "—"), ub.get("calls", "—")))  # noqa: T201
    print(_row("cost_usd", f"${ua.get('cost_usd', 0):.4f}", f"${ub.get('cost_usd', 0):.4f}"))  # noqa: T201
    print(_row("apps scored", len(ra.get("applications", [])), len(rb.get("applications", []))))  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
