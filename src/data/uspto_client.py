"""USPTO Open Data Portal API client.

Thin, typed wrapper around the USPTO Open Data Portal (https://data.uspto.gov) with:
  * API-key auth
  * exponential-backoff retries on transient failures and rate limiting
  * a simple on-disk JSON cache so we never re-fetch the same document

This client only *fetches* raw documents. Parsing into structured form lives in
``office_action_parser.py`` and ``patent_fetcher.py`` so that retrieval/verification can always
re-derive structure from the cached raw source (closed-loop principle).
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_settings

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("data/cache/uspto")


class USPTOError(RuntimeError):
    """Raised when the USPTO API returns an unrecoverable error."""


class USPTOClient:
    """Client for the USPTO Open Data Portal API.

    Parameters
    ----------
    api_key:
        USPTO Open Data Portal key. Defaults to ``settings.uspto_api_key``.
    cache_dir:
        Directory for the on-disk response cache. Defaults to ``data/cache/uspto``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.uspto_api_key
        self.base_url = (base_url or settings.uspto_base_url).rstrip("/")
        self.cache_dir = cache_dir or _CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            timeout=timeout,
            headers={"X-API-KEY": self.api_key, "Accept": "application/json"},
        )

    # -- lifecycle ---------------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "USPTOClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- caching -----------------------------------------------------------------------------

    def _cache_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, key: str) -> Any | None:
        path = self._cache_path(key)
        if path.exists():
            logger.debug("USPTO cache hit: %s", key)
            return json.loads(path.read_text("utf-8"))
        return None

    def _write_cache(self, key: str, value: Any) -> None:
        self._cache_path(key).write_text(json.dumps(value), encoding="utf-8")

    # -- HTTP --------------------------------------------------------------------------------

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    )
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise USPTOError(
                "USPTO_API_KEY is not configured. Register at https://data.uspto.gov."
            )
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self._client.get(url, params=params)
        # 429 / 5xx are retryable; raise_for_status triggers the tenacity retry.
        if resp.status_code == 429 or resp.status_code >= 500:
            resp.raise_for_status()
        if resp.status_code >= 400:
            raise USPTOError(f"USPTO API {resp.status_code} for {url}: {resp.text[:200]}")
        return resp.json()

    def _get_cached(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        key = f"{path}?{json.dumps(params, sort_keys=True)}"
        cached = self._read_cache(key)
        if cached is not None:
            return cached
        data = self._get(path, params)
        self._write_cache(key, data)
        return data

    # -- public API --------------------------------------------------------------------------

    def search_applications(self, application_number: str) -> dict[str, Any]:
        """Look up an application by its number (returns metadata + document references)."""
        return self._get_cached(
            "/api/v1/patent/applications/search",
            params={"applicationNumberText": application_number},
        )

    def get_office_actions(self, application_number: str) -> list[dict[str, Any]]:
        """Return office-action document descriptors for an application."""
        data = self._get_cached(
            f"/api/v1/patent/applications/{application_number}/documents",
        )
        docs = data.get("documents", data.get("docBag", []))
        return [d for d in docs if _is_office_action(d)]

    def get_document_text(self, document_id: str) -> str:
        """Fetch the full text of a document (office action, etc.) by id."""
        data = self._get_cached(f"/api/v1/patent/documents/{document_id}")
        return _extract_text(data)

    def get_patent_full_text(self, patent_number: str) -> dict[str, Any]:
        """Fetch the full text (claims, spec, abstract) of a granted patent / publication."""
        normalized = patent_number.replace(",", "").replace(" ", "")
        return self._get_cached(f"/api/v1/patent/grants/{normalized}/full-text")

    def patent_exists(self, patent_number: str) -> bool:
        """Cheap existence check used by the citation verifier."""
        try:
            self.get_patent_full_text(patent_number)
            return True
        except USPTOError:
            return False


def _is_office_action(doc: dict[str, Any]) -> bool:
    code = (doc.get("documentCode") or doc.get("documentCodeText") or "").upper()
    desc = (doc.get("documentDescription") or "").lower()
    return code in {"CTNF", "CTFR", "CTAV"} or "office action" in desc


def _extract_text(doc: dict[str, Any]) -> str:
    for key in ("plainText", "text", "documentText", "content"):
        if isinstance(doc.get(key), str):
            return doc[key]
    return json.dumps(doc)
