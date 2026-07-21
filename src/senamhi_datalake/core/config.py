"""Core configuration for SENAMHI DataLake.

Uses pydantic-settings for environment-driven configuration.
Values can be overridden via .env file or environment variables.
"""
from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings

from functools import lru_cache


def _project_root() -> Path:
    """Resolve project root dynamically at call time, not import time."""
    return Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # ── Project identity ──────────────────────────────────────────────
    project_name: str = "SENAMHI DataLake"
    project_version: str = "2.0.0"
    project_description: str = (
        "Plataforma SaaS profesional para extracción, gestión "
        "y visualización de datos hidrometeorológicos del SENAMHI Perú"
    )

    # ── Database ──────────────────────────────────────────────────────
    database_url: str = ""
    database_url_sync: str = ""

    # ── Security ──────────────────────────────────────────────────────
    secret_key: str = "CHANGE-ME-IN-PRODUCTION-senamhi-datalake"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # ── SENAMHI scraper ───────────────────────────────────────────────
    senamhi_base_url: str = (
        "https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"
    )
    scraper_timeout_seconds: int = 30
    scraper_worker_timeout_seconds: int = 300
    scraper_poll_interval: float = 0.5
    execute_scraper_in_api: bool = False

    # ── Directories ───────────────────────────────────────────────────
    stations_file: str = ""
    output_dir: str = ""
    csv_dir: str = ""

    # ── CSV export ────────────────────────────────────────────────────
    csv_separator: str = ";"
    csv_encoding: str = "utf-8"

    # ── Logging ───────────────────────────────────────────────────────
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "case_sensitive": False}

    def _resolve_defaults(self) -> None:
        root = _project_root()
        # Use the project's own output/csv directory (data is self-contained)
        if not self.database_url:
            self.database_url = f"sqlite+aiosqlite:///{root / 'data' / 'senamhi.db'}"
        if not self.database_url_sync:
            self.database_url_sync = f"sqlite:///{root / 'data' / 'senamhi.db'}"
        if not self.stations_file:
            self.stations_file = str(root / "data" / "estaciones.json")
        if not self.output_dir:
            self.output_dir = str(root / "output")
        if not self.csv_dir:
            self.csv_dir = str(root / "output" / "csv")

    def model_post_init(self, __context) -> None:
        self._resolve_defaults()


settings = Settings()
