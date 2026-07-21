"""SENAMHI scraper integration — coordinates the zendriver-based engine.

ExtractionRunner.run() is the single entry-point used by the background
task in routers/extractions.py.  It:

1. Resolves the human-readable station name from the JSON catalog.
2. Fetches the full station record from the database so the scraper has
   all the metadata it needs (type, status, category, legacy_code, etc.).
3. Decides whether to launch a real scraping session or skip because the
   target file already exists on disk.
4. Delegates the actual browser automation to ScraperEngine.run().
5. Returns a unified result dict that the background task persists to the DB.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import settings

logger = logging.getLogger(__name__)


class ExtractionRunner:
    """Coordinate SENAMHI data extraction via the zendriver engine."""

    # ── Public API ────────────────────────────────────────────────────

    @staticmethod
    async def run(
        station_code: str,
        mode: str,
        year: int,
        *,
        month: Optional[int] = None,
        end_year: Optional[int] = None,
        consolidated: bool = True,
    ) -> Dict[str, Any]:
        """Launch a scraping session for *station_code* and return a result dict.

        The result dict always contains:
            station_code    str
            station_name    str
            mode            str
            year            int
            month           int | None
            end_year        int | None
            consolidated    bool
            file_generated  str   — absolute path of the main output CSV
            filename        str   — basename of file_generated
            file_exists     bool
            record_count    int
            scraping_run    bool  — True when zendriver was actually used
            skipped         bool  — True when file already existed and was kept
            error           str   — non-empty on failure
        """
        # ── 1. Resolve station name from JSON catalog ─────────────────
        station_name, station_data = await _resolve_station(station_code)

        # ── 2. Try to fetch full record from the DB ───────────────────
        # (gives us station_type, status, category, legacy_code)
        db_station = await _fetch_db_station(station_code)
        if db_station:
            station_data.update(
                {
                    "name": db_station.name,
                    "station_type": db_station.station_type,
                    "status": db_station.status,
                    "category": db_station.category,
                    "legacy_code": db_station.legacy_code or "",
                    "code": db_station.code,
                }
            )
            station_name = db_station.name

        # ── 3. Check if the exact target file already exists ──────────
        existing = _expected_output_file(
            station_name=station_name,
            mode=mode,
            year=year,
            month=month,
            end_year=end_year,
            consolidated=consolidated,
        )
        if existing and existing.exists():
            logger.info(
                "Archivo exacto ya existe para %s — usando datos locales",
                station_name,
            )
            record_count = _count_rows(existing)
            return _build_result(
                station_code=station_code,
                station_name=station_name,
                mode=mode,
                year=year,
                month=month,
                end_year=end_year,
                consolidated=consolidated,
                file_generated=str(existing),
                record_count=record_count,
                scraping_run=False,
                skipped=True,
                error="",
            )

        # ── 4. Run the real scraping session ──────────────────────────
        if not station_data.get("code"):
            return _build_result(
                station_code=station_code,
                station_name=station_name,
                mode=mode,
                year=year,
                month=month,
                end_year=end_year,
                consolidated=consolidated,
                file_generated="",
                record_count=0,
                scraping_run=False,
                skipped=False,
                error=(
                    f"Estación '{station_code}' no encontrada en el catálogo. "
                    "Verifica el código e intenta de nuevo."
                ),
            )

        mode_params = {
            "mode": mode,
            "year": year,
            "month": month,
            "end_year": end_year,
            "consolidated": consolidated,
        }

        logger.info("Iniciando scraping real para %s (modo=%s)", station_name, mode)

        try:
            from ..scraper.engine import ScraperEngine

            scrape_result = await ScraperEngine.run(
                station_data=station_data,
                mode_params=mode_params,
                output_dir=settings.csv_dir,
                csv_separator=settings.csv_separator,
                csv_encoding=settings.csv_encoding,
                timeout_seconds=float(settings.scraper_timeout_seconds),
                worker_timeout_seconds=float(settings.scraper_worker_timeout_seconds),
                poll_interval=float(settings.scraper_poll_interval),
                on_progress=lambda msg: logger.info("[scraper] %s", msg),
            )
        except ImportError:
            scrape_result = {
                "file_generated": "",
                "record_count": 0,
                "skipped": False,
                "files_written": [],
                "error": (
                    "zendriver no está instalado. "
                    "Ejecuta: pip install zendriver"
                ),
            }
        except Exception as exc:
            logger.exception("Error durante ScraperEngine.run()")
            scrape_result = {
                "file_generated": "",
                "record_count": 0,
                "skipped": False,
                "files_written": [],
                "error": str(exc),
            }

        file_generated = scrape_result.get("file_generated", "")
        filename = Path(file_generated).name if file_generated else ""

        return _build_result(
            station_code=station_code,
            station_name=station_name,
            mode=mode,
            year=year,
            month=month,
            end_year=end_year,
            consolidated=consolidated,
            file_generated=file_generated,
            record_count=scrape_result.get("record_count", 0),
            scraping_run=True,
            skipped=scrape_result.get("skipped", False),
            error=scrape_result.get("error", ""),
        )

    # ── File listing ──────────────────────────────────────────────────

    @staticmethod
    def list_output_files() -> List[Dict[str, Any]]:
        """Enumerate all CSV files in the output tree."""
        csv_root = Path(settings.csv_dir)
        if not csv_root.exists():
            return []

        files: List[Dict[str, Any]] = []
        for station_dir in sorted(csv_root.iterdir()):
            if not station_dir.is_dir():
                continue
            for csv_file in sorted(station_dir.glob("*.csv")):
                size_mb = csv_file.stat().st_size / (1024 * 1024)
                row_count = _count_rows(csv_file)
                files.append(
                    {
                        "station": station_dir.name,
                        "filename": csv_file.name,
                        "path": str(csv_file),
                        "size_mb": round(size_mb, 2),
                        "rows": row_count,
                    }
                )

        return files


# ── Private helpers ───────────────────────────────────────────────────


def _count_rows(filepath: Path) -> int:
    """Return the number of data rows (header excluded) in a CSV file."""
    try:
        with open(filepath, "r", encoding=settings.csv_encoding) as fh:
            return max(0, sum(1 for _ in fh) - 1)
    except Exception:
        return 0


def _expected_output_file(
    *,
    station_name: str,
    mode: str,
    year: int,
    month: Optional[int],
    end_year: Optional[int],
    consolidated: bool,
) -> Optional[Path]:
    """Return the deterministic CSV path for requests that map to one file."""
    clean_name = station_name.replace(" ", "")
    csv_root = Path(settings.csv_dir) / clean_name

    if mode == "month" and month is not None:
        filename = f"{clean_name}-{year:04d}{month:02d}.csv"
    elif mode == "year" and consolidated:
        filename = f"{clean_name}-{year}.csv"
    elif mode == "period" and consolidated:
        filename = f"{clean_name}-{year}-{end_year or year}.csv"
    else:
        return None

    return csv_root / filename


def _build_result(
    *,
    station_code: str,
    station_name: str,
    mode: str,
    year: int,
    month: Optional[int],
    end_year: Optional[int],
    consolidated: bool,
    file_generated: str,
    record_count: int,
    scraping_run: bool,
    skipped: bool,
    error: str,
) -> Dict[str, Any]:
    filename = Path(file_generated).name if file_generated else ""
    return {
        "station_code": station_code,
        "station_name": station_name,
        "mode": mode,
        "year": year,
        "month": month,
        "end_year": end_year,
        "consolidated": consolidated,
        "file_generated": file_generated,
        "filename": filename,
        "file_exists": bool(file_generated and Path(file_generated).exists()),
        "record_count": record_count,
        "scraping_run": scraping_run,
        "skipped": skipped,
        "error": error,
    }


async def _resolve_station(station_code: str):
    """Read `data/estaciones.json` and return (name, station_data_dict)."""
    station_name = station_code
    station_data: Dict[str, Any] = {"code": station_code}

    stations_file = Path(settings.stations_file)
    if not stations_file.exists():
        return station_name, station_data

    try:
        raw = json.loads(stations_file.read_text(encoding="utf-8"))
        for entry in raw:
            if entry.get("cod") == station_code:
                station_name = entry.get("nom", station_code).strip().title()
                station_data = {
                    "code": entry.get("cod", station_code),
                    "name": station_name,
                    "station_type": entry.get("ico", "M"),
                    "status": entry.get("estado", "DIFERIDO"),
                    "category": entry.get("cate", "CO"),
                    "legacy_code": entry.get("cod_old", ""),
                    "latitude": entry.get("lat", 0.0),
                    "longitude": entry.get("lon", 0.0),
                }
                break
    except Exception:
        logger.warning("No se pudo leer el catálogo de estaciones", exc_info=True)

    return station_name, station_data


async def _fetch_db_station(station_code: str):
    """Fetch a Station ORM instance from the database, or return None."""
    try:
        from sqlalchemy import select
        from ..core.database import async_session_factory
        from ..models.orm import Station

        async with async_session_factory() as db:
            result = await db.execute(
                select(Station).where(Station.code == station_code)
            )
            return result.scalar_one_or_none()
    except Exception:
        logger.warning("No se pudo consultar la BD para %s", station_code)
        return None
