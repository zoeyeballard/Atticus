"""FastAPI application entry point.

Run with: ``uvicorn src.main:app --reload``
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api.middleware import RequestContextMiddleware
from src.api.routes import analyses, analyze, audit, draft, health, interest, search, verify
from src.config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="Atticus",
    description="Verification-first AI assistant for USPTO office action responses.",
    version=__version__,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = settings.api_prefix
for module in (health, analyze, analyses, draft, search, verify, audit, interest):
    app.include_router(module.router, prefix=prefix)


_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if _STATIC_DIR.is_dir():
    # Tier-2 single-image mode: serve the built React frontend and fall back to index.html for
    # client-side routes (anything not under the API prefix).
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = _STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_STATIC_DIR / "index.html")

else:

    @app.get("/")
    def root() -> dict:
        return {"name": "Atticus", "version": __version__, "docs": "/docs"}


# --------------------------------------------------------------------------------------------
# CLI — ``python -m src.main analyze --application-number 16835899``
# Importing the module for uvicorn (``src.main:app``) does not run this.
# --------------------------------------------------------------------------------------------


def _cli() -> None:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(prog="atticus", description="Atticus CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze_cmd = sub.add_parser("analyze", help="Analyze an office action")
    src_group = analyze_cmd.add_mutually_exclusive_group(required=True)
    src_group.add_argument("--application-number", help="USPTO application number")
    src_group.add_argument("--file", help="Path to an office-action text file")
    src_group.add_argument("--text", help="Office-action text inline")
    analyze_cmd.add_argument(
        "--app-label", help="Record this application number when the source is --file/--text"
    )
    analyze_cmd.add_argument(
        "--no-llm", action="store_true", help="Deterministic parse only (no LLM, no verification)"
    )
    analyze_cmd.add_argument(
        "--allow-unpublished",
        action="store_true",
        help="Override the publication guard (authorized users only; unpublished apps are "
        "confidential under 35 U.S.C. 122(a))",
    )
    analyze_cmd.add_argument("--output-json", help="Write the result JSON to this path")

    verify_cmd = sub.add_parser("verify", help="Verify claims in office-action / draft text")
    vsrc = verify_cmd.add_mutually_exclusive_group(required=True)
    vsrc.add_argument("--file", help="Path to a text file to verify")
    vsrc.add_argument("--text", help="Text to verify inline")
    verify_cmd.add_argument("--output-json", help="Write the verification report to this path")

    draft_cmd = sub.add_parser("draft-response", help="Draft a response from an office action")
    dsrc = draft_cmd.add_mutually_exclusive_group(required=True)
    dsrc.add_argument("--application-number", help="USPTO application number")
    dsrc.add_argument("--file", help="Path to an office-action text file")
    draft_cmd.add_argument("--strategy", choices=["argue", "amend", "both"], default="argue")
    draft_cmd.add_argument("--allow-unpublished", action="store_true")
    draft_cmd.add_argument("--output-json", help="Write the draft to this path")

    args = parser.parse_args()

    if args.command == "verify":
        from pathlib import Path

        from src.verification import hallucination_detector

        text = Path(args.file).read_text("utf-8") if args.file else args.text
        report = hallucination_detector.verify_output(text)
        _emit(json.dumps({"verification": report.model_dump()}, indent=2, default=str),
              args.output_json)
        return

    if args.command == "draft-response":
        from pathlib import Path

        from src.data import office_action_parser
        from src.data.uspto_client import USPTOClient, USPTOError
        from src.generation.response_drafter import draft_response

        if args.application_number:
            try:
                with USPTOClient() as client:
                    if not args.allow_unpublished and not client.is_published(args.application_number):
                        print(f"error: {args.application_number} not published; use "  # noqa: T201
                              "--allow-unpublished if authorized.", file=sys.stderr)
                        sys.exit(3)
                    text = client.get_office_action_text(args.application_number)
            except USPTOError as exc:
                print(f"error: {exc}", file=sys.stderr)  # noqa: T201
                sys.exit(2)
        else:
            text = Path(args.file).read_text("utf-8")
        analysis = office_action_parser.parse(text, application_number=args.application_number)
        draft = draft_response(analysis, analysis_id="cli", strategy=args.strategy)
        _emit(json.dumps({"draft": draft.model_dump()}, indent=2, default=str), args.output_json)
        return

    if args.command == "analyze":
        from pathlib import Path

        from src.data import office_action_parser
        from src.data.uspto_client import USPTOClient, USPTOError

        if args.application_number:
            try:
                with USPTOClient() as client:
                    if not args.allow_unpublished and not client.is_published(
                        args.application_number
                    ):
                        print(  # noqa: T201
                            f"error: application {args.application_number} does not appear to be "
                            "published. Unpublished applications are confidential under 35 U.S.C. "
                            "122(a). Use --allow-unpublished if you are authorized.",
                            file=sys.stderr,
                        )
                        sys.exit(3)
                    text = client.get_office_action_text(args.application_number)
            except USPTOError as exc:
                print(f"error: {exc}", file=sys.stderr)  # noqa: T201
                sys.exit(2)
        elif args.file:
            text = Path(args.file).read_text("utf-8")
        else:
            text = args.text

        app_number = args.application_number or args.app_label
        analysis = office_action_parser.parse(
            text, application_number=app_number, use_llm=not args.no_llm
        )
        output = {"analysis": analysis.model_dump()}

        if not args.no_llm:
            from src.verification import hallucination_detector

            report = hallucination_detector.verify_output(analysis.raw_text or text)
            output["verification"] = report.model_dump()

        _emit(json.dumps(output, indent=2, default=str), args.output_json)


def _emit(payload: str, output_json: str | None) -> None:
    """Write JSON to a file (creating parents) or print it to stdout."""
    if output_json:
        from pathlib import Path

        Path(output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(output_json).write_text(payload, encoding="utf-8")
        print(f"wrote {output_json}")  # noqa: T201
    else:
        print(payload)  # noqa: T201


if __name__ == "__main__":
    _cli()
