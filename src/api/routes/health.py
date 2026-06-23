"""Health / readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from src import __version__
from src.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "anthropic_configured": settings.anthropic_configured,
        "uspto_configured": settings.uspto_configured,
        "generation_model": settings.generation_model,
        "verification_model": settings.verification_model,
    }
