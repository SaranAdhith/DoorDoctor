"""Database engine, session factory and declarative base."""

from collections.abc import Generator
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def now() -> datetime:
    """Current server wall-clock time as a naive datetime.

    Every timestamp in this MVP is stored naive and in the server's own
    timezone, and the client renders it as-is. A production deployment would
    store timezone-aware UTC and convert per user.
    """
    return datetime.now()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    from . import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
