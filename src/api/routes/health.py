"""Health / readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from src import __version__
from src.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    gemini = settings.llm_provider == "gemini"
    return {
        "status": "ok",
        "version": __version__,
        "llm_provider": settings.llm_provider,
        "llm_configured": settings.llm_configured,
        "anthropic_configured": settings.anthropic_configured,
        "gemini_configured": settings.gemini_configured,
        "uspto_configured": settings.uspto_configured,
        "generation_model": settings.gemini_generation_model if gemini else settings.generation_model,
        "verification_model": (
            settings.gemini_verification_model if gemini else settings.verification_model
        ),
    }
