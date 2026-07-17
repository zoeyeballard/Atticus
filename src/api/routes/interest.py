"""POST /interest — record an access-interest signup from the landing page.

Stores signups as JSON lines under ``data/interest/`` (gitignored). No client data, no LLM
involvement; just a quiet ledger of who asked to be written to.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["interest"])

_LEDGER = Path("data/interest/interest.jsonl")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InterestRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    organization: str = Field(default="", max_length=300)
    role: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=2000)


@router.post("/interest")
def register_interest(req: InterestRequest) -> dict:
    if not _EMAIL_RE.match(req.email.strip()):
        raise HTTPException(
            422,
            {
                "error": {
                    "code": "INVALID_EMAIL",
                    "message": "That email address does not look complete.",
                    "suggestion": "Please check it and try again.",
                }
            },
        )
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        **req.model_dump(),
    }
    with _LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    logger.info("Interest signup recorded (%s)", req.email)
    return {"recorded": True}
