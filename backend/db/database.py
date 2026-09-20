"""
TrustGate Flex — Database Configuration
SQLAlchemy engine, session factory, and FastAPI dependency.
"""

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# ── Load environment variables ─────────────────────────
load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./trustgate.db")

# ── Engine ─────────────────────────────────────────────
# For SQLite we need check_same_thread=False so FastAPI's
# thread-pool can share the connection.
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)


# Enable SQLite WAL mode & foreign keys for every connection.
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    """Enable WAL journal mode and foreign key enforcement for SQLite."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


# ── Session factory ────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ── Declarative Base ───────────────────────────────────
Base = declarative_base()


# ── FastAPI dependency ─────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for a single request lifecycle.
    Usage in FastAPI:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Table creation helper ──────────────────────────────
def create_all_tables() -> None:
    """
    Create every table defined via Base.metadata.
    Call this once at application startup or from a CLI script.
    Must import all model modules BEFORE calling so that
    SQLAlchemy's metadata registry is fully populated.
    """
    # Import models so they are registered with Base.metadata
    import backend.models.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    print("✔ All tables created successfully.")
