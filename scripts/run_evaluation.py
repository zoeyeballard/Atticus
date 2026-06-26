"""Run the Atticus evaluation harness and save a timestamped report.

Usage:
    python scripts/run_evaluation.py --mode no-llm   # deterministic parsing only (free)
    python scripts/run_evaluation.py --mode full     # + LLM enrichment + verification (needs credits)
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from tests.evaluation.hallucination_eval import run_evaluation

logging.basicConfig(level="INFO")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Atticus evaluation harness.")
    parser.add_argument("--mode", choices=["no-llm", "full"], default="no-llm")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = run_evaluation(mode=args.mode, timestamp=timestamp)
    print(summary.to_markdown())  # noqa: T201
    print(f"\nSaved: results/evaluations/eval_{args.mode}_{timestamp}.json")  # noqa: T201


if __name__ == "__main__":
    main()
