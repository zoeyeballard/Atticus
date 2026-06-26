"""Score deterministic parse results against ground truth.

Compares each ``results/<app>_analysis.json`` against ``data/test_applications.json`` (ground
truth read independently from the office-action text) and prints per-application and aggregate
parsing-accuracy metrics: rejection-type accuracy, statutory-basis recall/precision, claim-set
accuracy, and phantom-rejection rate.

Usage: python scripts/score_parsing.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

_REGISTRY = Path("data/test_applications.json")
_RESULTS = Path("results")


def _norm_basis(b: str) -> str:
    """Collapse parsed bases to the ground-truth granularity (e.g. '112(a)' -> '112')."""
    return b.split("(")[0]


def score_application(result: dict, expected: dict) -> dict:
    analysis = result["analysis"]

    # Rejection type
    rt_ok = analysis.get("rejection_type") == expected.get("rejection_type")

    # Bases (normalize parsed 112(a)/112(b) -> 112 to match ground truth granularity)
    found_bases = {_norm_basis(r["rejection_basis"]) for r in analysis.get("rejections", [])}
    expected_bases = set(expected.get("ground_truth_bases", []))
    bases_recall = len(found_bases & expected_bases) / len(expected_bases) if expected_bases else 1.0
    bases_precision = len(found_bases & expected_bases) / len(found_bases) if found_bases else 1.0
    phantom = sorted(found_bases - expected_bases)

    # Claim sets per basis
    found_claims: dict[str, set[int]] = {}
    for r in analysis.get("rejections", []):
        found_claims.setdefault(_norm_basis(r["rejection_basis"]), set()).add(r["claim_number"])
    claim_matches, claim_total = 0, 0
    for b, claims in expected.get("ground_truth_claims", {}).items():
        claim_total += 1
        if set(found_claims.get(b, set())) == set(claims):
            claim_matches += 1
    claim_acc = claim_matches / claim_total if claim_total else 1.0

    return {
        "rejection_type_correct": rt_ok,
        "bases_recall": bases_recall,
        "bases_precision": bases_precision,
        "claim_set_accuracy": claim_acc,
        "phantom_bases": phantom,
    }


def main() -> int:
    if not _REGISTRY.exists():
        print("Missing data/test_applications.json — run discovery first.")  # noqa: T201
        return 1
    registry = json.loads(_REGISTRY.read_text())

    agg = {"rt": [], "recall": [], "precision": [], "claims": []}
    print(f"{'APP':>10}  {'TYPE':>5}  {'RECALL':>6}  {'PREC':>6}  {'CLAIMS':>6}  PHANTOM")
    for entry in registry:
        app = entry["application_number"]
        rp = _RESULTS / f"{app}_analysis.json"
        if not rp.exists():
            print(f"{app:>10}  (no results file — run the pipeline first)")  # noqa: T201
            continue
        s = score_application(json.loads(rp.read_text()), entry)
        agg["rt"].append(s["rejection_type_correct"])
        agg["recall"].append(s["bases_recall"])
        agg["precision"].append(s["bases_precision"])
        agg["claims"].append(s["claim_set_accuracy"])
        print(  # noqa: T201
            f"{app:>10}  {'OK' if s['rejection_type_correct'] else 'X':>5}  "
            f"{s['bases_recall']:>6.0%}  {s['bases_precision']:>6.0%}  "
            f"{s['claim_set_accuracy']:>6.0%}  {','.join(s['phantom_bases']) or '-'}"
        )

    n = max(len(agg["rt"]), 1)
    print("\nAGGREGATE")  # noqa: T201
    print(f"  rejection-type accuracy : {sum(agg['rt'])/n:.0%}")  # noqa: T201
    print(f"  basis recall (mean)     : {sum(agg['recall'])/n:.0%}")  # noqa: T201
    print(f"  basis precision (mean)  : {sum(agg['precision'])/n:.0%}")  # noqa: T201
    print(f"  claim-set accuracy (mean): {sum(agg['claims'])/n:.0%}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
