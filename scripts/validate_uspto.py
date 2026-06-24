"""Step 1: validate the USPTO ODP client against the live API.

Usage:
    export USPTO_API_KEY=your-key
    python scripts/validate_uspto.py 16835899

Runs the Step-1 test sequence from NEXT_STEPS.md: application metadata → documents list →
office-action text. Prints a concise pass/fail report so you can confirm the client works (and
spot any ODP path/schema drift) before seeding.
"""

from __future__ import annotations

import sys

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from src.config import get_settings
from src.data.uspto_client import USPTOClient, USPTOError

# A real application with a non-final rejection (CTNF), useful as a default smoke test.
# Note: application states change over time — if this one has been allowed/abandoned and no
# longer exposes an office action, pass a current one as the first CLI argument.
DEFAULT_APP = "19531961"


def _check(label: str, fn) -> bool:
    try:
        result = fn()
    except USPTOError as exc:
        print(f"  ✗ {label}: {exc}")  # noqa: T201
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ {label}: unexpected {type(exc).__name__}: {exc}")  # noqa: T201
        return False
    print(f"  ✓ {label}")  # noqa: T201
    return result if isinstance(result, bool) else True


def main(application_number: str) -> int:
    settings = get_settings()
    if not settings.uspto_configured:
        print("USPTO_API_KEY is not set. Get one at https://data.uspto.gov/myodp.")  # noqa: T201
        return 1

    print(f"Validating USPTO ODP client against application {application_number}\n")  # noqa: T201
    with USPTOClient() as client:
        ok = True

        def _meta():
            data = client.get_application(application_number)
            print(f"    art_unit={_dig(data, 'applicationMetaData', 'groupArtUnitNumber')}")  # noqa: T201
            return True

        def _docs():
            docs = client.get_documents(application_number)
            print(f"    {len(docs)} documents; {len(client.get_office_actions(application_number))} office action(s)")  # noqa: T201
            return True

        def _oa_text():
            text = client.get_office_action_text(application_number)
            print(f"    office action text: {len(text)} chars")  # noqa: T201
            print("    " + text[:200].replace("\n", " "))  # noqa: T201
            return bool(text)

        ok &= _check("get_application", _meta)
        ok &= _check("get_documents", _docs)
        ok &= _check("get_office_action_text", _oa_text)

    print("\nAll checks passed." if ok else "\nSome checks failed — see above.")  # noqa: T201
    return 0 if ok else 1


def _dig(data: dict, *keys: str):
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


if __name__ == "__main__":
    app = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_APP
    sys.exit(main(app))
