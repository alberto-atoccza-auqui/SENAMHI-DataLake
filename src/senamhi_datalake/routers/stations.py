"""/api/stations — Browse the station catalog and query data."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..core.security import get_current_user
from ..schemas.dto import (
    DataPreviewOut,
    DataQueryOut,
    DataQueryRequest,
    StationListOut,
    StationOut,
)
from ..services.catalog import DataReader, StationCatalog

router = APIRouter(prefix="/api/stations", tags=["stations"])


@router.get("/with-data")
async def stations_with_data(
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return which stations have CSV data available."""
    from ..services.catalog import DataReader
    with_data = DataReader.stations_with_data()
    return {"stations_with_data": sorted(with_data)}


@router.get("/filters")
async def get_filters(
    db: AsyncSession = Depends(get_session),
) -> dict:
    return await StationCatalog.filter_options(db)


@router.get("", response_model=StationListOut)
async def list_stations(
    type: Optional[str] = Query(default=None, description="M or H"),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_session),
) -> StationListOut:
    stations = await StationCatalog.list_stations(
        db, station_type=type, status=status, search=search
    )
    return StationListOut(
        total=len(stations),
        stations=[StationOut.model_validate(s) for s in stations],
    )


@router.get("/{code}", response_model=StationOut)
async def get_station(
    code: str, db: AsyncSession = Depends(get_session)
) -> StationOut:
    station = await StationCatalog.get_by_code(db, code)
    if station is None:
        raise HTTPException(status_code=404, detail="Estación no encontrada")
    return StationOut.model_validate(station)


@router.get("/{code}/data/preview", response_model=DataPreviewOut)
async def preview_data(
    code: str, db: AsyncSession = Depends(get_session)
) -> DataPreviewOut:
    station = await StationCatalog.get_by_code(db, code)
    if station is None:
        raise HTTPException(status_code=404, detail="Estación no encontrada")

    filepath = DataReader._resolve_file(station.name)
    if filepath is None:
        raise HTTPException(status_code=404, detail="No hay datos CSV para esta estación")

    preview = DataReader.preview(filepath)
    return DataPreviewOut(
        station_name=station.name,
        station_code=station.code,
        **preview,
    )


@router.post("/{code}/data/query", response_model=DataQueryOut)
async def query_data(
    code: str,
    body: DataQueryRequest,
    db: AsyncSession = Depends(get_session),
) -> DataQueryOut:
    station = await StationCatalog.get_by_code(db, code)
    if station is None:
        raise HTTPException(status_code=404, detail="Estación no encontrada")

    filepath = DataReader._resolve_file(station.name)
    if filepath is None:
        return DataQueryOut(
            station_code=code,
            station_name=station.name,
            headers=[],
            total_rows=0,
            rows=[],
        )

    result = DataReader.query(
        filepath,
        start_date=body.start_date,
        end_date=body.end_date,
        limit=body.limit,
        offset=body.offset,
    )
    return DataQueryOut(
        station_code=code,
        station_name=station.name,
        **result,
    )
