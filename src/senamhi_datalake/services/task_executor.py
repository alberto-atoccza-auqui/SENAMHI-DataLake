"""Execution service for queued SENAMHI extraction tasks."""
from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from ..core.config import settings
from ..core.database import async_session_factory
from ..models.orm import ExtractionTask, Station, TaskStatus
from .extraction import ExtractionRunner

logger = logging.getLogger(__name__)


def _file_log(task_id: int, msg: str) -> None:
    logger.info(msg)
    try:
        log_path = Path(settings.output_dir) / "logs" / "scraper.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"[{ts}] [task={task_id}] {msg}\n")
    except Exception:
        pass


def _params_from_task(task: ExtractionTask, station: Station) -> dict[str, Any]:
    try:
        raw_params = json.loads(task.parameters_json or "{}")
    except json.JSONDecodeError:
        raw_params = {}

    return {
        "station_code": station.code,
        "mode": task.mode,
        "year": task.year,
        "month": task.month,
        "end_year": task.end_year,
        "consolidated": raw_params.get("consolidated", True),
    }


async def execute_extraction_task(
    task_id: int,
    params: Optional[dict[str, Any]] = None,
) -> None:
    """Run one queued extraction task and persist its final state."""
    _file_log(task_id, f"=== TAREA {task_id} INICIADA === params={params or '<db>'}")

    async with async_session_factory() as db:
        task = (
            await db.execute(
                select(ExtractionTask).where(ExtractionTask.id == task_id)
            )
        ).scalar_one_or_none()
        if task is None:
            _file_log(task_id, f"Tarea {task_id} no encontrada en BD")
            return

        station = (
            await db.execute(select(Station).where(Station.id == task.station_id))
        ).scalar_one_or_none()
        if station is None:
            task.status = TaskStatus.FAILED.value
            task.error_detail = "La estación asociada a esta tarea ya no existe."
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            _file_log(task_id, "FALLIDO: estación asociada no encontrada")
            return

        if params is None:
            params = _params_from_task(task, station)

        task.status = TaskStatus.RUNNING.value
        task.error_detail = ""
        task.completed_at = None
        await db.commit()
        _file_log(task_id, "Status -> RUNNING")

        try:
            result = await ExtractionRunner.run(**params)
            _file_log(task_id, f"ExtractionRunner.run() terminó: {result}")

            if result.get("error"):
                task.status = TaskStatus.FAILED.value
                task.error_detail = str(result["error"])
                _file_log(task_id, f"ERROR en resultado: {result['error']}")
            elif (
                not result.get("file_generated")
                and result.get("record_count", 0) == 0
                and not result.get("skipped")
            ):
                task.status = TaskStatus.FAILED.value
                task.error_detail = (
                    "No se pudieron obtener datos ni generar el archivo de extracción."
                )
                _file_log(task_id, "FALLIDO: sin registros ni archivo generado")
            else:
                task.status = TaskStatus.COMPLETED.value
                task.output_file = result.get("file_generated", "")
                task.record_count = result.get("record_count", 0)
                _file_log(
                    task_id,
                    f"COMPLETADO: {task.record_count} registros -> {task.output_file}",
                )

        except Exception as exc:
            tb = traceback.format_exc()
            task.status = TaskStatus.FAILED.value
            task.error_detail = f"{exc}\n\n{tb}"
            _file_log(task_id, f"EXCEPCION no capturada: {exc}\n{tb}")

        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        _file_log(task_id, f"=== TAREA {task_id} FINALIZADA: {task.status} ===")
