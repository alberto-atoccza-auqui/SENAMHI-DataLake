"""Async database engine and session factory.

Provides the SQLAlchemy 2.0-style async engine, a session maker,
and a FastAPI dependency for injecting sessions into route handlers.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields a DB session and closes it afterwards."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_all_tables() -> None:
    """Create all tables defined by ORM models (safe for first-run)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
