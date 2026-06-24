"""FastAPI application entry point.

Run with: ``uvicorn src.main:app --reload``
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api.middleware import RequestContextMiddleware
from src.api.routes import analyze, audit, draft, health, search, verify
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
for module in (health, analyze, draft, search, verify, audit):
    app.include_router(module.router, prefix=prefix)


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
        "--no-llm", action="store_true", help="Deterministic parse only (no LLM, no verification)"
    )

    args = parser.parse_args()

    if args.command == "analyze":
        from src.data import office_action_parser
        from src.data.uspto_client import USPTOClient, USPTOError

        if args.application_number:
            try:
                with USPTOClient() as client:
                    text = client.get_office_action_text(args.application_number)
            except USPTOError as exc:
                print(f"error: {exc}", file=sys.stderr)  # noqa: T201
                sys.exit(2)
        elif args.file:
            from pathlib import Path

            text = Path(args.file).read_text("utf-8")
        else:
            text = args.text

        analysis = office_action_parser.parse(
            text, application_number=args.application_number, use_llm=not args.no_llm
        )
        output = {"analysis": analysis.model_dump()}

        if not args.no_llm:
            from src.verification import hallucination_detector

            report = hallucination_detector.verify_output(analysis.raw_text or text)
            output["verification"] = report.model_dump()

        print(json.dumps(output, indent=2, default=str))  # noqa: T201


if __name__ == "__main__":
    _cli()
