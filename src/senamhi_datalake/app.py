"""SENAMHI DataLake — FastAPI application entrypoint.

Start with:  uvicorn senamhi_datalake.app:create_app --factory --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.database import create_all_tables
from .routers import auth, extractions, stations, system
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    await create_all_tables()

    # Import station catalog on first run
    from .core.database import async_session_factory
    from .services.catalog import StationCatalog

    async with async_session_factory() as db:
        imported = await StationCatalog.import_from_json(db)
        if imported > 0:
            print(f"📡 {imported} estaciones importadas al catálogo")

    yield


def create_app() -> FastAPI:
    """Factory: build and configure the FastAPI instance."""
    app = FastAPI(
        title=settings.project_name,
        version=settings.project_version,
        description=settings.project_description,
        lifespan=_lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # ── CORS ──────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────
    app.include_router(auth.router)
    app.include_router(stations.router)
    app.include_router(extractions.router)
    app.include_router(system.router)

    # ── Serve frontend SPA (mounted last so /api/* takes priority) ───
    web_dir = Path(__file__).resolve().parent.parent.parent / "web"
    if web_dir.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(web_dir), html=True),
            name="frontend",
        )

    return app
