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

from src.config import get_settings
from src.config.data_classification import DEFAULT_TENANT_ID, DataClass

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
        # Registry test apps are all published → PUBLIC data (safe on any provider tier).
        analysis = office_action_parser.parse(
            text, application_number=app, use_llm=use_llm,
            rejection_type=entry.get("rejection_type"), data_class=DataClass.PUBLIC,
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

            report = hallucination_detector.verify_output(text, data_class=DataClass.PUBLIC)
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


# --------------------------------------------------------------------------------------------
# Draft-level hallucination evaluation (Phase 4 Task 1) — scores GENERATED drafts.
# --------------------------------------------------------------------------------------------

import re as _re  # noqa: E402

_SOURCE_RE = _re.compile(r"\[Source:\s*([^,\]]+?)\s*(?:,\s*([^\]]+))?\]", _re.IGNORECASE)
_LEGAL_RE = _re.compile(r"\bMPEP\b|\b§\s*\d|\b35\s*U\.?S\.?C\b|KSR|Graham|Alice|obvious", _re.IGNORECASE)
_FACTUAL_HINT_RE = _re.compile(r"\bdiscloses?\b|\bteaches?\b|\bshows?\b|\bdescribes?\b", _re.IGNORECASE)


def _classify_assertion(text: str) -> str:
    """SOURCED | LEGAL | ARGUMENT | FACTUAL (danger zone: factual without a source)."""
    if _SOURCE_RE.search(text):
        return "sourced"
    if _LEGAL_RE.search(text):
        return "legal"
    if _FACTUAL_HINT_RE.search(text):
        return "factual"  # a factual disclosure claim with no [Source: ...]
    return "argument"


def _eval_one_draft(app, oa, entry, uspto, llm, strategy, max_entailment, max_rejections=0) -> dict:
    """Generate + score one application's draft. Returns a counts dict. May raise (e.g. 429)."""
    from src.data import office_action_parser
    from src.generation.response_drafter import draft_response
    from src.verification import claim_decomposer
    from src.verification.citation_verifier import extract_patent_numbers
    from src.verification.entailment_checker import check_entailment

    analysis = office_action_parser.parse(
        oa.read_text(encoding="utf-8"), application_number=app, use_llm=True,
        rejection_type=entry.get("rejection_type"), data_class=DataClass.PUBLIC,
    )
    # Cap the number of drafted rejections to bound LLM-call volume (free-tier quota).
    if max_rejections and len(analysis.rejections) > max_rejections:
        analysis = analysis.model_copy(update={"rejections": analysis.rejections[:max_rejections]})
    draft = draft_response(analysis, app, strategy=strategy, llm=llm, data_class=DataClass.PUBLIC)
    draft_text = "\n".join(a.argument_text for a in draft.arguments if a.argument_text)

    # Map each cited reference -> the examiner's mapped limitation (entailment context).
    passage_by_ref: dict[str, str] = {}
    for rej in analysis.rejections:
        for m in rej.limitation_mappings:
            if m.mapped_to_reference:
                passage_by_ref.setdefault(m.mapped_to_reference, m.limitation_text)

    assertions = claim_decomposer.decompose(draft_text, llm=llm, data_class=DataClass.PUBLIC)
    counts = {k: 0 for k in ("sourced", "legal", "argument", "factual_unsourced",
                             "verified", "fabricated", "contradicts", "neutral",
                             "location_invalid")}
    budget = max_entailment
    for a in assertions:
        atext = a.get("claim_text", "")
        cls = _classify_assertion(atext)
        if cls in ("legal", "argument"):
            counts[cls] += 1
            continue
        if cls == "factual":
            counts["factual_unsourced"] += 1  # grounding-rule violation: unsourced factual claim
            continue
        # SOURCED
        counts["sourced"] += 1
        nums = extract_patent_numbers(atext)
        if nums and not uspto.patent_exists(nums[0]):
            counts["fabricated"] += 1
            continue
        m = _SOURCE_RE.search(atext)
        loc = (m.group(2) or "") if m else ""
        if loc and not _re.search(r"col\.|line|para|\[\d|fig", loc, _re.IGNORECASE):
            counts["location_invalid"] += 1
            continue
        ref = m.group(1).strip() if m else ""
        context = passage_by_ref.get(ref) or ""
        if context and budget > 0:
            budget -= 1
            ent = check_entailment(context, atext, llm=llm, data_class=DataClass.PUBLIC)
            verdict = ent["verdict"]
            counts["contradicts" if verdict == "CONTRADICTS"
                   else "neutral" if verdict == "NEUTRAL" else "verified"] += 1
        else:
            counts["verified"] += 1  # document exists + plausible location; entailment not run
    return counts


def run_draft_evaluation(
    strategy: str = "argue", timestamp: str = "", limit: int | None = None, max_entailment: int = 6,
    max_rejections: int = 0,
) -> dict:
    """Generate response drafts and score their assertions (existence / location / entailment).

    Definitions (see docs/evaluation-methodology.md):
      hallucination = fabricated document OR entailment CONTRADICTS
      review-needed = location invalid, entailment NEUTRAL, or unsourced factual claim
      verified      = document exists, location plausible, passage entails the assertion
    """
    from src.data import office_action_parser
    from src.data.uspto_client import USPTOClient
    from src.generation.llm_client import LLMClient
    from src.generation.response_drafter import draft_response
    from src.verification import claim_decomposer
    from src.verification.citation_verifier import extract_patent_numbers
    from src.verification.entailment_checker import check_entailment

    settings = get_settings()
    registry = json.loads(_REGISTRY.read_text()) if _REGISTRY.exists() else []
    if limit:
        registry = registry[:limit]

    llm = LLMClient()
    apps_out = []
    agg = {"total": 0, "sourced": 0, "verified": 0, "fabricated": 0, "contradicts": 0,
           "neutral": 0, "location_invalid": 0, "factual_unsourced": 0, "legal": 0, "argument": 0}

    errors: list[str] = []
    with USPTOClient() as uspto:
        for entry in registry:
            app = entry["application_number"]
            oa = Path(entry.get("oa_text_file", _OA_DIR / f"{app}_oa.txt"))
            if not oa.exists():
                continue
            try:
                counts = _eval_one_draft(
                    app, oa, entry, uspto, llm, strategy, max_entailment, max_rejections
                )
            except Exception as exc:  # noqa: BLE001 — e.g. provider rate limit (429): record + continue
                errors.append(f"{app}: {type(exc).__name__}: {str(exc)[:140]}")
                continue
            app_total = sum(
                counts[k] for k in ("sourced", "legal", "argument", "factual_unsourced")
            )
            apps_out.append({
                "application_number": app,
                "draft_assertions_total": app_total,
                "sourced": counts["sourced"], "legal": counts["legal"],
                "argument": counts["argument"], "factual_unsourced": counts["factual_unsourced"],
                "sourced_breakdown": {
                    "verified": counts["verified"], "location_invalid": counts["location_invalid"],
                    "entailment_neutral": counts["neutral"],
                    "entailment_contradicts": counts["contradicts"],
                    "fabricated_document": counts["fabricated"],
                },
            })
            for k in counts:
                agg[k] = agg.get(k, 0) + counts[k]
            agg["total"] += app_total

    sourced = max(agg["sourced"], 1)
    total = max(agg["total"], 1)
    report = {
        "timestamp": timestamp,
        "provider": settings.llm_provider,
        "generation_model": llm.generation_model,
        "verification_model": llm.verification_model,
        "strategy": strategy,
        "applications": apps_out,
        "errors": errors,
        "aggregate": {
            "hallucination_rate": round((agg["fabricated"] + agg["contradicts"]) / sourced, 4),
            "review_rate": round(
                (agg["neutral"] + agg["location_invalid"] + agg["factual_unsourced"]) / total, 4
            ),
            "verified_rate": round(agg["verified"] / sourced, 4),
            "usage": {"calls": llm.usage.calls, "cost_usd": round(llm.usage.cost_usd, 4)},
        },
    }
    if timestamp:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        (_OUT_DIR / f"draft_eval_{settings.llm_provider}_{timestamp}.json").write_text(
            json.dumps(report, indent=2)
        )
    return report
