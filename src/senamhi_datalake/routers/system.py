"""/api/system, /api/health and /api/files — system status, health check, file ops."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_session
from ..models.orm import ExtractionTask
from ..schemas.dto import FileInfo, FileListOut, SystemStatusOut
from ..services.catalog import StationCatalog
from ..services.extraction import ExtractionRunner

router = APIRouter(tags=["system"])


# ── Health check ──────────────────────────────────────────────────────
# NOTE: This endpoint lives here (in a router included BEFORE the StaticFiles
# mount) to ensure it is always reachable even when StaticFiles is mounted
# at "/" with html=True.

@router.get("/api/health")
async def health():
    """Simple liveness probe — returns 200 OK when the server is running."""
    return {
        "status": "ok",
        "project": settings.project_name,
        "version": settings.project_version,
    }


# ── System status ─────────────────────────────────────────────────────


@router.get("/api/system/status", response_model=SystemStatusOut)
async def system_status(
    db: AsyncSession = Depends(get_session),
) -> SystemStatusOut:
    stations = await StationCatalog.count(db)

    total_tasks = (
        await db.execute(
            select(func.count()).select_from(ExtractionTask)
        )
    ).scalar() or 0

    active_tasks = (
        await db.execute(
            select(func.count()).select_from(ExtractionTask).where(
                ExtractionTask.status.in_(["pending", "running"])
            )
        )
    ).scalar() or 0

    db_path = (
        Path(settings.database_url_sync.replace("sqlite:///", ""))
        if settings.database_url_sync.startswith("sqlite")
        else None
    )
    db_mb = (
        round(os.path.getsize(db_path) / (1024 * 1024), 2)
        if db_path and db_path.exists()
        else 0.0
    )

    return SystemStatusOut(
        project=settings.project_name,
        version=settings.project_version,
        stations_count=stations,
        total_extractions=total_tasks,
        active_extractions=active_tasks,
        database_size_mb=db_mb,
        data_path=settings.csv_dir,
    )


# ── File browser ──────────────────────────────────────────────────────


@router.get("/api/files/open-folder")
async def open_data_folder():
    """Return the CSV data path and open it in Windows Explorer.

    Uses os.startfile() which is the correct Windows API for launching
    a path with its associated application (Explorer for directories).
    Backslash-normalises the path so Explorer handles it correctly.
    """
    data_path = Path(settings.csv_dir).resolve()
    data_path.mkdir(parents=True, exist_ok=True)
    path_str = str(data_path)

    try:
        # os.startfile is Windows-only; fall back gracefully on other OSes.
        os.startfile(path_str)  # type: ignore[attr-defined]
    except AttributeError:
        # Non-Windows: try xdg-open (Linux) or open (macOS)
        import subprocess
        try:
            subprocess.Popen(["xdg-open", path_str])
        except FileNotFoundError:
            subprocess.Popen(["open", path_str])
    except Exception:
        pass  # Explorer failed silently — path is still returned to the client

    return {"path": path_str, "action": "opened"}


@router.get("/api/files", response_model=FileListOut)
async def list_files() -> FileListOut:
    entries = [
        FileInfo(**f) for f in ExtractionRunner.list_output_files()
    ]
    return FileListOut(total=len(entries), files=entries)


@router.get("/api/files/download/{station}/{filename}")
async def download_file(station: str, filename: str):
    filepath = Path(settings.csv_dir) / station / filename
    if not filepath.exists():
        return JSONResponse(
            status_code=404, content={"error": "Archivo no encontrado"}
        )
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="text/csv",
    )


@router.delete("/api/files/{station}/{filename}")
async def delete_file(station: str, filename: str):
    """Delete a CSV file from disk. Also removes the station folder if empty."""
    filepath = Path(settings.csv_dir) / station / filename
    if not filepath.exists():
        return JSONResponse(
            status_code=404, content={"error": "Archivo no encontrado"}
        )
    try:
        filepath.unlink()
        # Remove empty parent folder
        parent = filepath.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
        return {"deleted": True, "path": str(filepath), "action": "deleted"}
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"No se pudo eliminar: {e}"}
        )
