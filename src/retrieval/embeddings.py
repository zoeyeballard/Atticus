"""Embedding generation.

Wraps a sentence-transformers model (``all-MiniLM-L6-v2`` baseline). The model is loaded lazily
and memoized so importing this module is cheap and offline-safe — heavy ML deps are only touched
when embeddings are actually requested.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from src.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    """Load and cache a sentence-transformers model."""
    from sentence_transformers import SentenceTransformer  # heavy import, deferred

    logger.info("Loading embedding model: %s", model_name)
    return SentenceTransformer(model_name)


class Embedder:
    """Generates normalized embedding vectors for text."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().embedding_model

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = _load_model(self.model_name)
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]
