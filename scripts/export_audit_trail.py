"""Export the audit trail for an analysis as JSON for offline review."""

from __future__ import annotations

import json
import sys

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from src.db.repositories import get_repository


def main(analysis_id: str) -> None:
    repo = get_repository()
    events = repo.get_audit_trail(analysis_id)
    print(json.dumps({"analysis_id": analysis_id, "events": events}, indent=2))  # noqa: T201


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/export_audit_trail.py <analysis_id>")  # noqa: T201
        sys.exit(1)
    main(sys.argv[1])
