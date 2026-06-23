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
