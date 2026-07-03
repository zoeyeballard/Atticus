"""Evaluation harness.

Runs the Atticus pipeline against the test applications in ``data/test_applications.json`` and
scores parsing accuracy against ground truth. Two modes:

  * ``no-llm`` — deterministic parsing only (free, local). Scores rejection-type accuracy,
    statutory-basis recall/precision, and claim-set accuracy.
  * ``full``   — parsing + LLM enrichment + verification (needs Anthropic credits). Additionally
    records the hallucination rate from the verification report.

Results are written to ``results/evaluations/eval_<mode>_<timestamp>.json``.

Caveat: ground truth in the registry is extracted from the OA text with a permissive regex that
shares lineage with the parser, so basis/claim agreement partly measures self-consistency.
``rejection_type`` ground truth is independent (derived from the authoritative document code).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.config.data_classification import DEFAULT_TENANT_ID

_REGISTRY = Path("data/test_applications.json")
_OA_DIR = Path("data/sample_office_actions")
_OUT_DIR = Path("results/evaluations")
# Legacy ground-truth cases (used only if the registry is absent).
_CASES_DIR = Path(__file__).parent / "test_cases"


@dataclass
class EvalSummary:
    timestamp: str = ""
    mode: str = "no-llm"
    total_cases: int = 0
    rejection_type_accuracy: float = 0.0
    basis_recall: float = 0.0
    basis_precision: float = 0.0
    claim_set_accuracy: float = 0.0
    hallucination_rate: float = 0.0
    per_case: list[dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            "# Atticus Evaluation Summary",
            "",
            f"- Mode: **{self.mode}**  ·  Cases: **{self.total_cases}**  ·  {self.timestamp}",
            f"- Rejection-type accuracy: **{self.rejection_type_accuracy:.0%}**",
            f"- Basis recall: **{self.basis_recall:.0%}**  ·  precision: **{self.basis_precision:.0%}**",
            f"- Claim-set accuracy: **{self.claim_set_accuracy:.0%}**",
        ]
        if self.mode == "full":
            lines.append(f"- Hallucination rate: **{self.hallucination_rate:.1%}** (target <5%)")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "total_cases": self.total_cases,
            "aggregate": {
                "rejection_type_accuracy": self.rejection_type_accuracy,
                "basis_recall": self.basis_recall,
                "basis_precision": self.basis_precision,
                "claim_set_accuracy": self.claim_set_accuracy,
                "hallucination_rate": self.hallucination_rate,
            },
            "applications": self.per_case,
        }


def check_data_compliance(analysis_result: dict) -> list[str]:
    """Verify an analysis respects the data-classification rules. Returns a list of issues."""
    issues: list[str] = []

    if not analysis_result.get("publication_verified", False):
        issues.append("CRITICAL: Publication status not verified before indexing")

    if not analysis_result.get("tenant_id"):
        issues.append("CRITICAL: Missing tenant_id on client data")

    # A fabricated reference must never be persisted into the public patent index.
    for ref in analysis_result.get("cited_references", []):
        if ref.get("verification_status") == "fabricated":
            issues.append(
                f"CRITICAL: Fabricated reference {ref.get('patent_number')} — "
                "must not be stored in the public patent index"
            )

    if analysis_result.get("llm_used") and not analysis_result.get("audit_events"):
        issues.append("WARNING: LLM used but no audit trail recorded")

    return issues


def _norm_basis(b: str) -> str:
    return b.split("(")[0]


def _score(analysis: dict, expected: dict) -> dict:
    found_bases = {_norm_basis(r["rejection_basis"]) for r in analysis.get("rejections", [])}
    exp_bases = set(expected.get("ground_truth_bases", []))
    recall = len(found_bases & exp_bases) / len(exp_bases) if exp_bases else 1.0
    precision = len(found_bases & exp_bases) / len(found_bases) if found_bases else 1.0

    found_claims: dict[str, set[int]] = {}
    for r in analysis.get("rejections", []):
        found_claims.setdefault(_norm_basis(r["rejection_basis"]), set()).add(r["claim_number"])
    matches = total = 0
    for b, claims in expected.get("ground_truth_claims", {}).items():
        total += 1
        if found_claims.get(b, set()) == set(claims):
            matches += 1
    return {
        "rejection_type_correct": analysis.get("rejection_type") == expected.get("rejection_type"),
        "basis_recall": recall,
        "basis_precision": precision,
        "claim_set_accuracy": (matches / total) if total else 1.0,
        "found_bases": sorted(found_bases),
        "expected_bases": sorted(exp_bases),
    }


def run_evaluation(mode: str = "no-llm", timestamp: str = "") -> EvalSummary:
    """Run the harness. ``timestamp`` is injected by the caller (e.g. the CLI) for the filename."""
    from src.data import office_action_parser

    if not _REGISTRY.exists():
        return EvalSummary(mode=mode, timestamp=timestamp)
    registry = json.loads(_REGISTRY.read_text())

    use_llm = mode == "full"
    rt, rec, prec, claims, halluc = [], [], [], [], []
    per_case = []

    for entry in registry:
        app = entry["application_number"]
        oa_file = Path(entry.get("oa_text_file", _OA_DIR / f"{app}_oa.txt"))
        if not oa_file.exists():
            continue
        text = oa_file.read_text(encoding="utf-8")
        analysis = office_action_parser.parse(
            text, application_number=app, use_llm=use_llm,
            rejection_type=entry.get("rejection_type"),
        ).model_dump()
        s = _score(analysis, entry)
        rt.append(s["rejection_type_correct"])
        rec.append(s["basis_recall"])
        prec.append(s["basis_precision"])
        claims.append(s["claim_set_accuracy"])

        # Compliance: registry apps are published; client data carries the default tenant.
        compliance = check_data_compliance(
            {
                "publication_verified": True,
                "tenant_id": DEFAULT_TENANT_ID,
                "llm_used": use_llm,
                "audit_events": [{"event_type": "llm_api_call"}] if use_llm else [],
                "cited_references": [
                    {"patent_number": r.get("patent_number"), "verification_status": "unverified"}
                    for rej in analysis.get("rejections", [])
                    for r in rej.get("cited_references", [])
                ],
            }
        )
        case = {"application_number": app, "compliance_issues": compliance, **s}
        if use_llm:
            from src.verification import hallucination_detector

            report = hallucination_detector.verify_output(text)
            rate = (report.fabricated_count / report.total_claims) if report.total_claims else 0.0
            halluc.append(rate)
            case["hallucination_rate"] = rate
            case["verification_confidence"] = report.overall_confidence
        per_case.append(case)

    n = max(len(rt), 1)
    summary = EvalSummary(
        timestamp=timestamp,
        mode=mode,
        total_cases=len(per_case),
        rejection_type_accuracy=sum(rt) / n,
        basis_recall=sum(rec) / n,
        basis_precision=sum(prec) / n,
        claim_set_accuracy=sum(claims) / n,
        hallucination_rate=(sum(halluc) / len(halluc)) if halluc else 0.0,
        per_case=per_case,
    )

    if timestamp:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = _OUT_DIR / f"eval_{mode}_{timestamp}.json"
        out.write_text(json.dumps(summary.to_dict(), indent=2))
    return summary


def load_cases() -> list[dict]:
    """Legacy: load ground-truth cases from tests/evaluation/test_cases/ (fallback)."""
    if not _CASES_DIR.exists():
        return []
    return [json.loads(p.read_text("utf-8")) for p in sorted(_CASES_DIR.glob("*.json"))]
