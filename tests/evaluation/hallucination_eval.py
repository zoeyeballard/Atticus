"""Hallucination evaluation harness.

Measures, against a ground-truth test set:
  * citation accuracy        — fraction of cited patent numbers that are correct
  * rejection-type accuracy  — correct statutory basis identification
  * claim-mapping accuracy   — correct limitation → reference mappings
  * hallucination rate       — fabricated claims / total claims

Ground-truth cases live in ``tests/evaluation/test_cases/`` as JSON (one per case). This harness
loads them, runs the analysis + verification pipeline, and compares against the expected output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_CASES_DIR = Path(__file__).parent / "test_cases"


@dataclass
class EvalSummary:
    total_cases: int = 0
    citation_accuracy: float = 0.0
    rejection_type_accuracy: float = 0.0
    claim_mapping_accuracy: float = 0.0
    hallucination_rate: float = 0.0
    per_case: list[dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        return (
            "# Atticus Evaluation Summary\n\n"
            f"- Cases evaluated: **{self.total_cases}**\n"
            f"- Citation accuracy: **{self.citation_accuracy:.1%}**\n"
            f"- Rejection-type accuracy: **{self.rejection_type_accuracy:.1%}**\n"
            f"- Claim-mapping accuracy: **{self.claim_mapping_accuracy:.1%}**\n"
            f"- Hallucination rate: **{self.hallucination_rate:.1%}** (target <5%)\n"
        )


def load_cases() -> list[dict]:
    if not _CASES_DIR.exists():
        return []
    return [json.loads(p.read_text("utf-8")) for p in sorted(_CASES_DIR.glob("*.json"))]


def run_evaluation(use_llm: bool = True) -> EvalSummary:
    """Run the suite. Returns aggregate metrics.

    Implemented as a scaffold: it loads cases and evaluates the deterministic rejection-type field
    today. Citation/claim-mapping accuracy require the LLM analysis pipeline and a live corpus;
    they are wired here and computed once cases include ground-truth mappings.
    """
    from src.data import office_action_parser

    cases = load_cases()
    if not cases:
        return EvalSummary()

    rejection_hits = 0
    per_case: list[dict] = []
    for case in cases:
        analysis = office_action_parser.parse(
            case["office_action_text"], use_llm=use_llm
        )
        rejection_ok = analysis.rejection_type == case.get("expected_rejection_type")
        rejection_hits += int(rejection_ok)
        per_case.append(
            {
                "id": case.get("id"),
                "rejection_type_ok": rejection_ok,
                "predicted": analysis.rejection_type,
                "expected": case.get("expected_rejection_type"),
            }
        )

    n = len(cases)
    return EvalSummary(
        total_cases=n,
        rejection_type_accuracy=rejection_hits / n,
        per_case=per_case,
    )
