"""Idempotent schema migrations for the POC.

For a real deployment we'd use Alembic. For the POC, a list of
`ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` statements
is enough and safe to re-run.

Run with:  python -m app.migrations
"""

from sqlalchemy import text

from app.db import engine

MIGRATIONS: list[str] = [
    # Step 5.1
    "ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS workflow_id VARCHAR(255)",
    "CREATE INDEX IF NOT EXISTS ix_transcripts_workflow_id "
    "ON transcripts(workflow_id)",
]


def main() -> None:
    with engine.begin() as conn:
        for sql in MIGRATIONS:
            conn.execute(text(sql))
    print(f"Applied {len(MIGRATIONS)} migration statement(s).")


if __name__ == "__main__":
    main()