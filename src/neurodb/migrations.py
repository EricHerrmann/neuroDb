from datetime import datetime, timezone

from sqlalchemy import Engine, text


def get_schema_version(engine: Engine) -> int:
    with engine.connect() as conn:
        try:
            row = conn.execute(
                text("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
            ).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0


def apply_migrations(engine: Engine, migrations: dict[int, callable]) -> None:
    """Apply any pending migrations in version order. Idempotent."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """))
        conn.commit()

    current = get_schema_version(engine)
    pending = sorted(v for v in migrations if v > current)

    for version in pending:
        with engine.connect() as conn:
            migrations[version](conn)
            conn.execute(
                text("INSERT INTO schema_migrations (version, applied_at) VALUES (:v, :at)"),
                {"v": version, "at": datetime.now(timezone.utc).isoformat()},
            )
            conn.commit()
