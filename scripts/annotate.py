"""Create a blank ground-truth annotation template for an application.

Usage:
    python scripts/annotate.py --application 19531961

Creates data/ground_truth_v2/<app>.yaml with a blank template and prints the path to the cached
office-action text to read. The annotation must be done COLD — from your own reading of the OA,
without looking at parser/LLM output. This is the independent ground truth the scorer measures
against (Phase 4 Task 3).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

_GT_DIR = Path("data/ground_truth_v2")
_OA_DIR = Path("data/sample_office_actions")

_TEMPLATE = """\
# Ground-truth annotation — fill in from your OWN reading of the office action.
# Do NOT look at parser or LLM output while annotating.
application_number: "{app}"
annotator: ""            # your name
date: ""                 # YYYY-MM-DD
minutes_spent: 0

rejection_type: ""       # non-final | final | advisory

rejections:
  # one block per (statutory basis) group as the examiner presented it
  - basis: ""            # "101" | "102" | "103" | "112(a)" | "112(b)" | "dp"
    claim_numbers: []    # e.g. [1, 2, 3]
    primary_reference: ""    # e.g. "US10,234,567" (empty for 101/112)
    secondary_references: [] # e.g. ["US11,345,678"]
    notes: ""

objections: []           # claim objections (not rejections), free text
notes: ""
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a blank ground-truth annotation template.")
    parser.add_argument("--application", required=True, help="Application number")
    args = parser.parse_args()
    app = args.application

    _GT_DIR.mkdir(parents=True, exist_ok=True)
    out = _GT_DIR / f"{app}.yaml"
    if out.exists():
        print(f"Annotation already exists: {out}")  # noqa: T201
    else:
        out.write_text(_TEMPLATE.format(app=app), encoding="utf-8")
        print(f"Created blank template: {out}")  # noqa: T201

    oa = _OA_DIR / f"{app}_oa.txt"
    if oa.exists():
        print(f"Read the office action here: {oa}  ({oa.stat().st_size} bytes)")  # noqa: T201
    else:
        print(f"WARNING: no cached OA text at {oa} — fetch it first.")  # noqa: T201
    return 0


if __name__ == "__main__":
    _sys.exit(main())
