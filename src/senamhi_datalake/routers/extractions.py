"""/api/extractions — Schedule, track and list extraction tasks."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_session
from ..core.security import get_current_user
from ..models.orm import ExtractionTask, Station, TaskStatus
from ..schemas.dto import (
    ExtractionRequest,
    ExtractionStatusOut,
    ExtractionTaskOut,
)
from ..services.catalog import StationCatalog
from ..services.task_executor import execute_extraction_task

router = APIRouter(prefix="/api/extractions", tags=["extractions"])


async def _execute_task(task_id: int, params: dict) -> None:
    """Backward-compatible background hook for opt-in in-process execution."""
    await execute_extraction_task(task_id, params)


@router.post("", response_model=ExtractionTaskOut)
async def create_extraction(
    body: ExtractionRequest,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    _: Optional[str] = Depends(get_current_user),
) -> ExtractionTaskOut:
    station = await StationCatalog.get_by_code(db, body.station_code)
    if station is None:
        raise HTTPException(status_code=404, detail="Estación no encontrada")

    # Prevent duplicate extractions for the same station + mode + period
    existing = (
        await db.execute(
            select(ExtractionTask).where(
                ExtractionTask.station_id == station.id,
                ExtractionTask.mode == body.mode,
                ExtractionTask.year == body.year,
                ExtractionTask.month == body.month,
                ExtractionTask.end_year == body.end_year,
                ExtractionTask.status.in_(["pending", "running"]),
            )
        )
    ).scalar_one_or_none()
    if existing:
        stn_name = station.name
        return ExtractionTaskOut(
            id=existing.id,
            station_id=existing.station_id,
            station_name=stn_name,
            mode=existing.mode,
            status=existing.status,
            year=existing.year,
            month=existing.month,
            end_year=existing.end_year,
            created_at=existing.created_at,
            completed_at=existing.completed_at,
        )

    task = ExtractionTask(
        station_id=station.id,
        mode=body.mode,
        year=body.year,
        month=body.month,
        end_year=body.end_year,
        parameters_json=json.dumps(body.model_dump()),
        status=TaskStatus.PENDING.value,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    if settings.execute_scraper_in_api:
        bg.add_task(
            _execute_task,
            task.id,
            {
                "station_code": body.station_code,
                "mode": body.mode,
                "year": body.year,
                "month": body.month,
                "end_year": body.end_year,
                "consolidated": body.consolidated,
            },
        )

    return ExtractionTaskOut(
        id=task.id,
        station_id=task.station_id,
        station_name=station.name,
        mode=task.mode,
        status=task.status,
        year=task.year,
        month=task.month,
        end_year=task.end_year,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


@router.get("/status", response_model=ExtractionStatusOut)
async def extraction_status(
    db: AsyncSession = Depends(get_session),
) -> ExtractionStatusOut:
    counts = dict.fromkeys(
        ["pending", "running", "completed", "failed"], 0
    )
    rows = (
        await db.execute(
            select(ExtractionTask.status, func.count()).group_by(
                ExtractionTask.status
            )
        )
    ).all()
    for s, c in rows:
        if s in counts:
            counts[s] = c

    recent_rows = (
        await db.execute(
            select(ExtractionTask)
            .order_by(ExtractionTask.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    recent: list[ExtractionTaskOut] = []
    for t in recent_rows:
        stn = (
            await db.execute(
                select(Station).where(Station.id == t.station_id)
            )
        ).scalar_one_or_none()
        recent.append(
            ExtractionTaskOut(
                id=t.id,
                station_id=t.station_id,
                station_name=stn.name if stn else "",
                mode=t.mode,
                status=t.status,
                year=t.year,
                month=t.month,
                end_year=t.end_year,
                output_file=t.output_file,
                record_count=t.record_count,
                error_detail=t.error_detail,
                created_at=t.created_at,
                completed_at=t.completed_at,
            )
        )

    return ExtractionStatusOut(
        pending=counts["pending"],
        running=counts["running"],
        completed=counts["completed"],
        failed=counts["failed"],
        recent=recent,
    )


@router.get("/tasks", response_model=list[ExtractionTaskOut])
async def list_tasks(
    limit: int = 50,
    db: AsyncSession = Depends(get_session),
) -> list[ExtractionTaskOut]:
    tasks = (
        await db.execute(
            select(ExtractionTask)
            .order_by(ExtractionTask.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    results: list[ExtractionTaskOut] = []
    for t in tasks:
        stn = (
            await db.execute(
                select(Station).where(Station.id == t.station_id)
            )
        ).scalar_one_or_none()
        results.append(
            ExtractionTaskOut(
                id=t.id,
                station_id=t.station_id,
                station_name=stn.name if stn else "",
                mode=t.mode,
                status=t.status,
                year=t.year,
                month=t.month,
                end_year=t.end_year,
                output_file=t.output_file,
                record_count=t.record_count,
                error_detail=t.error_detail,
                created_at=t.created_at,
                completed_at=t.completed_at,
            )
        )
    return results


@router.delete("/tasks")
async def clear_tasks(
    include_active: bool = False,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Clear extraction history rows.

    By default this removes only completed/failed rows so a running worker is
    not invalidated from the UI. Use include_active=true for a full reset.
    """
    statuses = ["completed", "failed"]
    if include_active:
        statuses.extend(["pending", "running"])

    result = await db.execute(
        delete(ExtractionTask).where(ExtractionTask.status.in_(statuses))
    )
    await db.commit()
    return {
        "deleted": result.rowcount or 0,
        "include_active": include_active,
    }


@router.get("/{task_id}", response_model=ExtractionTaskOut)
async def get_task(
    task_id: int, db: AsyncSession = Depends(get_session)
) -> ExtractionTaskOut:
    task = (
        await db.execute(
            select(ExtractionTask).where(ExtractionTask.id == task_id)
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    stn = (
        await db.execute(
            select(Station).where(Station.id == task.station_id)
        )
    ).scalar_one_or_none()
    return ExtractionTaskOut(
        id=task.id,
        station_id=task.station_id,
        station_name=stn.name if stn else "",
        mode=task.mode,
        status=task.status,
        year=task.year,
        month=task.month,
        end_year=task.end_year,
        output_file=task.output_file,
        record_count=task.record_count,
        error_detail=task.error_detail,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )
