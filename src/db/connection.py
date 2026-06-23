"""Database connection management.

A minimal psycopg connection helper. The vector store opens its own connections (it needs the
pgvector type registered); this module covers structured-data access for analyses and audit logs.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from src.config import get_settings

logger = logging.getLogger(__name__)


@contextmanager
def get_connection(dsn: str | None = None):
    """Yield a psycopg connection, committing on success and rolling back on error."""
    import psycopg  # deferred so importing this module needs no live DB

    dsn = dsn or get_settings().database_url
    conn = psycopg.connect(dsn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
