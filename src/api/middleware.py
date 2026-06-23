"""Request logging, error handling, and audit-trail middleware."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("atticus.api")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id, log timing, and convert uncaught errors to clean JSON."""

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 — last-resort handler
            logger.exception("Unhandled error [req=%s] %s %s", request_id, request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "request_id": request_id},
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "[req=%s] %s %s -> %s (%.1fms)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
