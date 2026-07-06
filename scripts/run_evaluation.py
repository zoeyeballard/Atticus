"""Run the Atticus evaluation harness and save a timestamped report.

Usage:
    python scripts/run_evaluation.py --mode no-llm            # deterministic parsing only (free)
    python scripts/run_evaluation.py --mode full              # + LLM enrichment + verification
    python scripts/run_evaluation.py --mode draft --strategy argue [--limit N]  # draft-level
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from tests.evaluation.hallucination_eval import run_draft_evaluation, run_evaluation

logging.basicConfig(level="INFO")


def _print_draft_table(report: dict) -> None:
    print(f"\n# Draft-level Hallucination Eval — provider={report['provider']} "  # noqa: T201
          f"model={report['generation_model']}  ({report['timestamp']})")
    print(f"{'APP':>10} {'ASSERTS':>8} {'SOURCED':>8} {'VERIF':>6} {'FAB':>4} "  # noqa: T201
          f"{'CONTRA':>7} {'NEUTRAL':>8} {'UNSRCD':>7}")
    for a in report["applications"]:
        b = a["sourced_breakdown"]
        print(f"{a['application_number']:>10} {a['draft_assertions_total']:>8} "  # noqa: T201
              f"{a['sourced']:>8} {b['verified']:>6} {b['fabricated_document']:>4} "
              f"{b['entailment_contradicts']:>7} {b['entailment_neutral']:>8} "
              f"{a['factual_unsourced']:>7}")
    agg = report["aggregate"]
    print(f"\n  verified rate     : {agg['verified_rate']:.1%}")  # noqa: T201
    print(f"  review rate       : {agg['review_rate']:.1%}")  # noqa: T201
    print(f"  hallucination rate: {agg['hallucination_rate']:.1%}  (fabricated + contradicts / sourced)")  # noqa: T201
    print(f"  usage             : {agg['usage']['calls']} calls, ${agg['usage']['cost_usd']:.4f}")  # noqa: T201


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Atticus evaluation harness.")
    parser.add_argument("--mode", choices=["no-llm", "full", "draft"], default="no-llm")
    parser.add_argument("--strategy", choices=["argue", "amend", "both"], default="argue")
    parser.add_argument("--limit", type=int, default=None, help="Max apps (draft mode)")
    parser.add_argument("--max-rejections", type=int, default=0,
                        help="Cap drafted rejections per app to bound LLM calls (0 = no cap)")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.mode == "draft":
        report = run_draft_evaluation(strategy=args.strategy, timestamp=timestamp, limit=args.limit,
                                      max_rejections=args.max_rejections)
        _print_draft_table(report)
        print(f"\nSaved: results/evaluations/draft_eval_{report['provider']}_{timestamp}.json")  # noqa: T201
        return

    summary = run_evaluation(mode=args.mode, timestamp=timestamp)
    print(summary.to_markdown())  # noqa: T201
    print(f"\nSaved: results/evaluations/eval_{args.mode}_{timestamp}.json")  # noqa: T201


if __name__ == "__main__":
    main()
