"""Run the hallucination evaluation suite against the ground-truth test set."""

from __future__ import annotations

import logging

from tests.evaluation.hallucination_eval import run_evaluation

logging.basicConfig(level="INFO")

if __name__ == "__main__":
    summary = run_evaluation()
    print(summary.to_markdown())  # noqa: T201
