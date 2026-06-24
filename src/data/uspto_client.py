"""USPTO Open Data Portal (ODP) API client.

Targets the **new** ODP at ``api.uspto.gov`` (the legacy Developer Hub was decommissioned
2026-06-05). Provides:
  * API-key auth via the ``X-Api-Key`` header
  * exponential-backoff retries on transient failures and rate limiting (HTTP 429)
  * a simple on-disk JSON cache so we never re-fetch the same document
  * application-number normalization (ODP wants digits only, e.g. ``16835899``)

Endpoint paths are centralized in ``_Endpoints`` so they can be corrected against the live
Swagger docs (data.uspto.gov) in one place if the migration changed any of them.

This client only *fetches* raw documents. Parsing into structured form lives in
``office_action_parser.py`` and ``patent_fetcher.py`` so retrieval/verification can always
re-derive structure from the cached raw source (closed-loop principle).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
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


class _Endpoints:
    """ODP endpoint path templates (relative to the API base, which already ends in /api/v1).

    Paths are relative to ``base_url`` (which includes ``/api/v1``). Verified live against
    api.uspto.gov (2026-06): application metadata and documents work with an ``X-Api-Key`` header;
    the per-application ``office-actions/{citations,rejections}`` structured products return 403
    with a standard data.uspto.gov key, so office-action *text* is obtained by downloading the
    document (DOCX/PDF/XML) from each document's ``downloadOptionBag``.
    """

    APPLICATION = "patent/applications/{app}"
    DOCUMENTS = "patent/applications/{app}/documents"
    SEARCH = "patent/applications/search"
    GRANT_FULL_TEXT = "patent/grants/{patent}/full-text"


# Document codes that denote an office action in ODP document listings.
_OFFICE_ACTION_CODES = {"CTNF", "CTFR", "CTAV", "CTRS"}


class USPTOError(RuntimeError):
    """Raised when the USPTO API returns an unrecoverable error."""


def normalize_application_number(application_number: str) -> str:
    """Normalize an application number to ODP form (digits only).

    Accepts ``"16/835,899"``, ``"16835899"``, ``"US16835899"`` → ``"16835899"``.
    """
    return re.sub(r"[^0-9]", "", application_number or "")


def normalize_patent_number(patent_number: str) -> str:
    """Normalize a patent/publication number (drop separators and the leading country code)."""
    cleaned = re.sub(r"[\s,]", "", patent_number or "")
    return re.sub(r"^US", "", cleaned, flags=re.IGNORECASE)


class USPTOClient:
    """Client for the USPTO Open Data Portal API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.uspto_api_key
        # base_url already includes the /api/v1 prefix so individual paths stay clean.
        self.base_url = (base_url or settings.uspto_base_url).rstrip("/")
        self.cache_dir = cache_dir or _CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            timeout=timeout,
            headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
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
                "USPTO_API_KEY is not configured. Register at https://data.uspto.gov "
                "(requires a USPTO.gov account + one-time ID.me verification)."
            )
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self._client.get(url, params=params)
        # 429 (rate limit) / 5xx are retryable; raise_for_status triggers the tenacity retry.
        if resp.status_code == 429 or resp.status_code >= 500:
            logger.warning("USPTO %s for %s — backing off and retrying", resp.status_code, url)
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

    def _download(self, url: str) -> bytes:
        """Download a document artifact (PDF/DOCX/XML) from a downloadOptionBag URL."""
        resp = self._client.get(url, follow_redirects=True)
        if resp.status_code >= 400:
            raise USPTOError(f"USPTO download {resp.status_code} for {url}")
        return resp.content

    # -- application metadata & documents ----------------------------------------------------

    def get_application(self, application_number: str) -> dict[str, Any]:
        """Application file-wrapper object (filing date, status, art unit, examiner under
        ``applicationMetaData``). Returns the first entry of ``patentFileWrapperDataBag``."""
        app = normalize_application_number(application_number)
        data = self._get_cached(_Endpoints.APPLICATION.format(app=app))
        bag = data.get("patentFileWrapperDataBag") if isinstance(data, dict) else None
        if isinstance(bag, list) and bag:
            return bag[0]
        return data if isinstance(data, dict) else {}

    def get_documents(self, application_number: str) -> list[dict[str, Any]]:
        """All documents in the file wrapper for an application (the ODP ``documentBag``)."""
        app = normalize_application_number(application_number)
        data = self._get_cached(_Endpoints.DOCUMENTS.format(app=app))
        if isinstance(data, list):
            return data
        for key in ("documentBag", "documents", "docBag", "results"):
            if isinstance(data.get(key), list):
                return data[key]
        return []

    def get_office_actions(self, application_number: str) -> list[dict[str, Any]]:
        """Office-action document descriptors only, newest first."""
        docs = [d for d in self.get_documents(application_number) if _is_office_action(d)]
        return sorted(docs, key=_doc_date, reverse=True)

    def get_office_action_text(self, application_number: str) -> str:
        """Plain text of the most recent office action.

        ODP exposes OA documents only as downloadable artifacts (no inline text field), so we
        locate the latest OA document and extract text from its ``downloadOptionBag``. DOCX is
        preferred (clean text); XML next; PDF last (USPTO OA PDFs are usually scanned images with
        no text layer, so PDF extraction may yield little).
        """
        actions = self.get_office_actions(application_number)
        if not actions:
            raise USPTOError(
                f"No office action found for application {application_number}."
            )
        options = {
            o.get("mimeTypeIdentifier"): o.get("downloadUrl")
            for o in actions[0].get("downloadOptionBag", [])
        }
        for fmt in ("MS_WORD", "XML", "PDF"):
            url = options.get(fmt)
            if not url:
                continue
            try:
                text = _extract_document_text(self._download(url), fmt)
            except Exception as exc:  # noqa: BLE001 — try the next format
                logger.info("OA %s extract failed (%s); trying next format.", fmt, exc)
                continue
            if text and len(text.strip()) > 200:
                return text
        raise USPTOError(
            f"Could not extract office-action text for {application_number} "
            f"(formats available: {sorted(k for k in options if k)})."
        )

    # -- patents -----------------------------------------------------------------------------

    def get_patent_full_text(self, patent_number: str) -> dict[str, Any]:
        """Full text (claims, spec, abstract) of a granted patent / publication."""
        normalized = normalize_patent_number(patent_number)
        return self._get_cached(_Endpoints.GRANT_FULL_TEXT.format(patent=normalized))

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
    return code in _OFFICE_ACTION_CODES or "office action" in desc


def _doc_date(doc: dict[str, Any]) -> str:
    """Best-effort date key for sorting documents (lexicographic on ISO-ish dates)."""
    for key in ("officialDate", "mailDate", "documentDate", "createDateTime", "date"):
        if doc.get(key):
            return str(doc[key])
    return ""


def _strip_xml_tags(xml: str) -> str:
    """Convert an OOXML/USPTO XML body to plain text (paragraph-aware, tags removed)."""
    xml = re.sub(r"</w:p>", "\n", xml)  # Word paragraph breaks
    xml = re.sub(r"</(p|para|paragraph)>", "\n", xml, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", xml)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#167;", "§")
    return re.sub(r"[ \t]+", " ", text)


def _extract_document_text(blob: bytes, fmt: str) -> str:
    """Extract plain text from a downloaded OA artifact (DOCX / XML-tar / PDF)."""
    import io

    if fmt == "MS_WORD":
        import zipfile

        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            return _strip_xml_tags(z.read("word/document.xml").decode("utf-8", "ignore"))

    if fmt == "XML":
        # The ODP "xmlarchive" endpoint returns a tar archive containing the OA .xml.
        import tarfile

        try:
            with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
                member = next(m for m in tar.getmembers() if m.name.endswith(".xml"))
                return _strip_xml_tags(tar.extractfile(member).read().decode("utf-8", "ignore"))
        except tarfile.TarError:
            return _strip_xml_tags(blob.decode("utf-8", "ignore"))  # plain XML fallback

    if fmt == "PDF":
        from pypdf import PdfReader  # deferred; OA PDFs are often scanned (no text layer)

        reader = PdfReader(io.BytesIO(blob))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    return ""
