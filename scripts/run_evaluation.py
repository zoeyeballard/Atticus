"""Run the hallucination evaluation suite against the ground-truth test set."""

from __future__ import annotations

import logging

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from tests.evaluation.hallucination_eval import run_evaluation

logging.basicConfig(level="INFO")

if __name__ == "__main__":
    summary = run_evaluation()
    print(summary.to_markdown())  # noqa: T201
