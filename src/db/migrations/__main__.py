"""Entry point: ``python -m src.db.migrations``."""

from __future__ import annotations

import logging

from src.db.migrations import migration_files, run_migrations

logging.basicConfig(level="INFO", format="%(message)s")


def main() -> None:
    pending = migration_files()
    if not pending:
        print("No migration files found.")  # noqa: T201
        return
    applied = run_migrations()
    if applied:
        print(f"Applied {len(applied)} migration(s): {', '.join(applied)}")  # noqa: T201
    else:
        print("Database already up to date — nothing to apply.")  # noqa: T201


if __name__ == "__main__":
    main()
