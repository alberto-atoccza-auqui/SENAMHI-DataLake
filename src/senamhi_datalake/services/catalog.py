"""Station catalog and CSV data services."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.orm import Station


# ── Human-readable labels ─────────────────────────────────────────────

STATION_TYPE_LABELS: dict[str, str] = {
    "M": "Meteorológica",
    "H": "Hidrológica",
}

STATUS_LABELS: dict[str, str] = {
    "REAL": "Tiempo Real",
    "DIFERIDO": "Diferido",
    "AUTOMATICA": "Automática",
}

CATEGORY_LABELS: dict[str, str] = {
    "EAA": "Estación Automática Agrícola",
    "PE": "Pluviométrica Especial",
    "CP": "Climatológica Principal",
    "HLM": "Hidrológica con Limnígrafo",
    "MAP": "Meteorológica Aeroportuaria",
    "EHA": "Estación Hidrológica Automática",
    "EHMA": "Estación Hidrometeorológica Automática",
    "CO": "Climatológica Ordinaria",
    "EMA": "Estación Meteorológica Automática",
    "PLU": "Pluviométrica",
    "EAMA": "Estación Agrometeorológica Automática",
    "HLG": "Hidrológica con Limniógrafo",
}


# ═══════════════════════════════════════════════════════════════════════
#  Station Catalog
# ═══════════════════════════════════════════════════════════════════════


class StationCatalog:
    """Manage station records: import, query, filter options."""

    @staticmethod
    async def import_from_json(
        db: AsyncSession, json_path: Optional[str] = None
    ) -> int:
        """Load the official SENAMHI station catalog from a JSON file."""
        path = json_path or settings.stations_file
        if not os.path.exists(path):
            return 0

        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

        imported = 0
        for item in raw:
            exists = (
                await db.execute(
                    select(Station).where(Station.code == item["cod"])
                )
            ).scalar_one_or_none()
            if exists:
                continue

            db.add(
                Station(
                    code=item["cod"],
                    name=item.get("nom", "").strip().title(),
                    category=item.get("cate", ""),
                    station_type=item.get("ico", "M"),
                    status=item.get("estado", "DIFERIDO"),
                    latitude=item.get("lat", 0.0),
                    longitude=item.get("lon", 0.0),
                    legacy_code=item.get("cod_old", ""),
                )
            )
            imported += 1

        await db.commit()
        return imported

    @staticmethod
    async def list_stations(
        db: AsyncSession,
        *,
        station_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Station]:
        query = select(Station)
        if station_type:
            query = query.where(Station.station_type == station_type)
        if status:
            query = query.where(Station.status == status)
        if search:
            query = query.where(Station.name.ilike(f"%{search}%"))
        query = query.order_by(Station.name)
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def get_by_code(
        db: AsyncSession, code: str
    ) -> Optional[Station]:
        return (
            await db.execute(select(Station).where(Station.code == code))
        ).scalar_one_or_none()

    @staticmethod
    async def count(db: AsyncSession) -> int:
        result = await db.execute(select(func.count()).select_from(Station))
        return result.scalar() or 0

    @staticmethod
    async def filter_options(db: AsyncSession) -> dict:
        type_rows = (
            await db.execute(
                select(Station.station_type, func.count())
                .group_by(Station.station_type)
            )
        ).all()
        status_rows = (
            await db.execute(
                select(Station.status, func.count())
                .group_by(Station.status)
            )
        ).all()

        return {
            "station_types": [
                {"value": t, "label": STATION_TYPE_LABELS.get(t, t), "count": c}
                for t, c in type_rows
            ],
            "statuses": [
                {"value": s, "label": STATUS_LABELS.get(s, s), "count": c}
                for s, c in status_rows
            ],
            "categories": [
                {"value": k, "label": v}
                for k, v in CATEGORY_LABELS.items()
            ],
        }


# ═══════════════════════════════════════════════════════════════════════
#  CSV Data Reader
# ═══════════════════════════════════════════════════════════════════════


class DataReader:
    """Read and query CSV files produced by the scraper."""

    @staticmethod
    def _resolve_file(station_name: str, exact: bool = True) -> Optional[Path]:
        """Find the CSV directory and file for a station.

        Tries exact match first, then case-insensitive fallback.
        """
        clean = station_name.replace(" ", "")
        csv_root = Path(settings.csv_dir)

        if not csv_root.exists():
            return None

        # Exact match
        station_dir = csv_root / clean

        # Case-insensitive fallback
        if not station_dir.exists():
            for entry in csv_root.iterdir():
                if entry.is_dir() and entry.name.lower() == clean.lower():
                    station_dir = entry
                    break

        if not station_dir.exists():
            return None

        # Prefer the full-range consolidated file
        candidate = station_dir / f"{station_dir.name}-2000-2025.csv"
        if candidate.exists():
            return candidate

        # Fallback to any CSV present
        for child in station_dir.glob("*.csv"):
            return child
        return None

    @staticmethod
    def has_data(station_name: str) -> bool:
        """Check if a station has downloaded CSV data."""
        return DataReader._resolve_file(station_name) is not None

    @staticmethod
    def stations_with_data() -> set[str]:
        """Return set of station names that have data files."""
        csv_root = Path(settings.csv_dir)
        if not csv_root.exists():
            return set()
        return {d.name for d in csv_root.iterdir() if d.is_dir()}

    @staticmethod
    def preview(filepath: Path, max_sample: int = 10) -> dict:
        if not filepath.exists():
            return {"headers": [], "row_count": 0, "sample_rows": [], "date_range": None}

        rows: list[list[str]] = []
        headers: list[str] = []
        try:
            with open(filepath, "r", encoding=settings.csv_encoding) as fh:
                reader = csv.reader(fh, delimiter=settings.csv_separator)
                headers = next(reader, [])
                rows = [r for r in reader]
        except Exception:
            return {"headers": [], "row_count": 0, "sample_rows": [], "date_range": None}

        date_range = None
        if rows and len(rows[0]) >= 3 and rows[-1] and len(rows[-1]) >= 3:
            date_range = (
                f"{'-'.join(rows[0][:3])} → {'-'.join(rows[-1][:3])}"
            )

        return {
            "headers": headers,
            "row_count": len(rows),
            "sample_rows": rows[:max_sample],
            "date_range": date_range,
        }

    @staticmethod
    def query(
        filepath: Path,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> dict:
        if not filepath.exists():
            return {"headers": [], "total_rows": 0, "rows": []}

        headers: list[str] = []
        all_rows: list[list[str]] = []
        try:
            with open(filepath, "r", encoding=settings.csv_encoding) as fh:
                reader = csv.reader(fh, delimiter=settings.csv_separator)
                headers = next(reader, [])

                for row in reader:
                    if start_date or end_date:
                        try:
                            date_str = (
                                f"{row[0]}-{row[1].zfill(2)}-{row[2].zfill(2)}"
                            )
                            if start_date and date_str < start_date:
                                continue
                            if end_date and date_str > end_date:
                                continue
                        except (IndexError, ValueError):
                            pass
                    all_rows.append(row)
        except Exception:
            return {"headers": headers, "total_rows": 0, "rows": []}

        total = len(all_rows)
        page = all_rows[offset : offset + limit]
        result_rows = [dict(zip(headers, r)) for r in page]

        return {
            "headers": headers,
            "total_rows": total,
            "rows": result_rows,
        }
