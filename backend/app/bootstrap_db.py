"""One-shot schema bootstrap for the POC.

Run with:  python -m app.bootstrap_db
"""

from app.db import engine
from app.models import Base


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Schema ensured (tables: transcripts, tickets, ticket_embeddings, redacted_transcripts, transcript_chunks).")


if __name__ == "__main__":
    main()