"""Score the parser (and optionally the LLM analysis) against human ground truth (v2).

Usage:
    python scripts/score_against_ground_truth.py --ground-truth data/ground_truth_v2/
    python scripts/score_against_ground_truth.py --ground-truth data/ground_truth_v2/ --with-llm

Compares each human-annotated YAML against Atticus's output and reports basis-level precision/
recall and reference recall — separately for apps marked held_out vs. seen in the registry.
The deterministic parse is always scored ($0); the LLM analysis is scored only with --with-llm
(needs provider quota).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
import yaml

from src.data import office_action_parser

_REGISTRY = Path("data/test_applications.json")


def _norm_basis(b: str) -> str:
    return str(b).split("(")[0].strip()


def _norm_ref(r: str) -> str:
    import re

    return re.sub(r"[^0-9]", "", r or "")


def _held_out_map() -> dict[str, bool]:
    if not _REGISTRY.exists():
        return {}
    return {e["application_number"]: bool(e.get("held_out")) for e in json.loads(_REGISTRY.read_text())}


def _truth_from_yaml(gt: dict) -> tuple[set[str], set[str], str]:
    bases, refs = set(), set()
    for rej in gt.get("rejections") or []:
        b = _norm_basis(rej.get("basis", ""))
        if b:
            bases.add(b)
        for r in [rej.get("primary_reference", "")] + list(rej.get("secondary_references") or []):
            if _norm_ref(r):
                refs.add(_norm_ref(r))
    return bases, refs, (gt.get("rejection_type") or "").strip()


def _analysis_bases_refs(analysis) -> tuple[set[str], set[str]]:
    bases = {_norm_basis(r.rejection_basis.value) for r in analysis.rejections}
    refs = {
        _norm_ref(c.patent_number)
        for r in analysis.rejections
        for c in r.cited_references
        if _norm_ref(c.patent_number)
    }
    return bases, refs


def _prf(pred: set, truth: set) -> tuple[float, float]:
    if not truth:
        return (1.0, 1.0)
    tp = len(pred & truth)
    recall = tp / len(truth)
    precision = tp / len(pred) if pred else 1.0
    return precision, recall


def main() -> int:
    ap = argparse.ArgumentParser(description="Score parser/LLM against human ground truth.")
    ap.add_argument("--ground-truth", default="data/ground_truth_v2/")
    ap.add_argument("--with-llm", action="store_true", help="Also score the LLM analysis (uses quota)")
    args = ap.parse_args()

    gt_dir = Path(args.ground_truth)
    files = sorted(gt_dir.glob("*.yaml")) if gt_dir.exists() else []
    annotated = []
    for f in files:
        gt = yaml.safe_load(f.read_text()) or {}
        if gt.get("annotator"):  # only count filled-in annotations
            annotated.append((f.stem, gt))

    if not annotated:
        print(f"No completed annotations in {gt_dir} yet. Fill in the YAML files "  # noqa: T201
              "(annotator field non-empty) via scripts/annotate.py first.")
        return 0

    held = _held_out_map()
    buckets: dict[str, list] = {"seen": [], "held_out": []}
    oa_dir = Path("data/sample_office_actions")

    for app, gt in annotated:
        oa = oa_dir / f"{app}_oa.txt"
        if not oa.exists():
            continue
        text = oa.read_text(encoding="utf-8")
        t_bases, t_refs, t_type = _truth_from_yaml(gt)

        det = office_action_parser.parse(text, application_number=app, use_llm=False)
        d_bases, d_refs = _analysis_bases_refs(det)
        row = {"app": app, "type_ok": det.rejection_type == t_type,
               "det_basis_prf": _prf(d_bases, t_bases), "det_ref_recall": _prf(d_refs, t_refs)[1]}

        if args.with_llm:
            from src.config.data_classification import DataClass

            llm_a = office_action_parser.parse(text, application_number=app, use_llm=True,
                                               data_class=DataClass.PUBLIC)
            l_bases, l_refs = _analysis_bases_refs(llm_a)
            row["llm_basis_prf"] = _prf(l_bases, t_bases)
            row["llm_ref_recall"] = _prf(l_refs, t_refs)[1]

        buckets["held_out" if held.get(app) else "seen"].append(row)

    for name, rows in buckets.items():
        if not rows:
            continue
        print(f"\n=== {name.upper()} ({len(rows)} apps) ===")  # noqa: T201
        for r in rows:
            p, rec = r["det_basis_prf"]
            extra = ""
            if "llm_basis_prf" in r:
                lp, lr = r["llm_basis_prf"]
                extra = f"  | LLM basis P/R {lp:.0%}/{lr:.0%} ref-recall {r['llm_ref_recall']:.0%}"
            print(f"  {r['app']}: type={'OK' if r['type_ok'] else 'X'}  "  # noqa: T201
                  f"det basis P/R {p:.0%}/{rec:.0%}  ref-recall {r['det_ref_recall']:.0%}{extra}")
    return 0


if __name__ == "__main__":
    _sys.exit(main())
