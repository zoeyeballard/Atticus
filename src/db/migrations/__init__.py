"""SQL migrations.

Run all pending migrations with::

    python -m src.db.migrations

Migrations are plain ``NNN_name.sql`` files in this directory, applied in filename order. Each is
recorded in a ``schema_migrations`` table so re-running is idempotent.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.config import get_settings

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent

_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def migration_files() -> list[Path]:
    return sorted(_MIGRATIONS_DIR.glob("[0-9]*.sql"))


def run_migrations(dsn: str | None = None) -> list[str]:
    """Apply all not-yet-applied migrations. Returns the list of filenames applied."""
    import psycopg  # deferred so importing this package needs no live DB

    dsn = dsn or get_settings().database_url
    applied: list[str] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(_TRACKING_TABLE)
            cur.execute("SELECT filename FROM schema_migrations")
            done = {row[0] for row in cur.fetchall()}

        for path in migration_files():
            if path.name in done:
                logger.info("skip  %s (already applied)", path.name)
                continue
            logger.info("apply %s", path.name)
            with conn.cursor() as cur:
                cur.execute(path.read_text("utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
                )
            applied.append(path.name)
        conn.commit()
    return applied
