"""SENAMHI scraping engine — spawns scraper_worker.py in its OWN console window.

The worker is launched via Windows `start` so it gets:
- Its own visible terminal (you see Chromium & logs)
- Its own asyncio event loop (no conflicts with uvicorn)
- Complete independence from the server process

The engine polls the worker's result file until completion or timeout.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_POLL_SLEEP = 3        # seconds


class ScraperEngine:
    """Spawns worker in visible console, polls result file."""

    @staticmethod
    async def run(
        station_data: Dict[str, Any],
        mode_params: Dict[str, Any],
        *,
        output_dir: str,
        csv_separator: str = ";",
        csv_encoding: str = "utf-8",
        timeout_seconds: float = 45.0,
        worker_timeout_seconds: float = 300.0,
        poll_interval: float = 0.5,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:

        result: Dict[str, Any] = {
            "file_generated": "", "record_count": 0,
            "skipped": False, "options_count": 0,
            "files_written": [], "error": "",
        }

        def _log(msg: str) -> None:
            logger.info(msg)
            try:
                log_path = Path(output_dir).parent / "logs" / "scraper.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                import datetime
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.write(f"[{ts}] [engine] {msg}\n")
            except Exception:
                pass
            if on_progress:
                on_progress(msg)

        # ── Prepare worker files ──────────────────────────────────────
        worker_script = Path(__file__).parent / "scraper_worker.py"
        tmp_dir = Path(output_dir).parent / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        job_id = uuid.uuid4().hex[:8]
        params_file = tmp_dir / f"params_{job_id}.json"
        result_file = tmp_dir / f"result_{job_id}.json"

        payload = {
            "station_data": station_data, "mode_params": mode_params,
            "output_dir": output_dir, "csv_separator": csv_separator,
            "csv_encoding": csv_encoding, "timeout_seconds": timeout_seconds,
            "poll_interval": poll_interval,
        }
        params_file.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")

        # ── Launch worker in its own visible console ──────────────────
        python_exe = sys.executable
        project_root = str(Path(__file__).parent.parent.parent.parent)

        _log(f"Lanzando worker en ventana propia (ID: {job_id})...")

        if os.name == "nt":
            # CREATE_NEW_CONSOLE (0x10) opens a new visible terminal window
            # The worker runs independently; we ONLY poll the result file
            creationflags = 0x00000010  # CREATE_NEW_CONSOLE
            proc = subprocess.Popen(
                [python_exe, str(worker_script), str(params_file), str(result_file)],
                cwd=project_root,
                creationflags=creationflags,
            )
            _log(f"Worker lanzado (PID: {proc.pid}) — consola visible")
        else:
            proc = subprocess.Popen(
                [python_exe, str(worker_script), str(params_file), str(result_file)],
                cwd=project_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        _log(f"Worker PID: {proc.pid} — esperando resultado...")

        # ── Poll for result file ──────────────────────────────────────
        start = time.monotonic()
        last_progress = start

        total_timeout = max(float(worker_timeout_seconds), float(timeout_seconds))

        while time.monotonic() - start < total_timeout:
            # First check if result file exists
            if result_file.exists():
                # Give it a moment to finish writing
                await asyncio.sleep(0.5)
                break

            # Check if process died early
            if proc is not None:
                returncode = proc.poll()
                if returncode is not None:
                    _log(f"Worker terminó prematuramente con exit={returncode}")
                    await asyncio.sleep(1)
                    break

            # Progress update every 30s
            if time.monotonic() - last_progress > 30:
                elapsed = int(time.monotonic() - start)
                _log(f"Aún esperando worker ({elapsed}s)...")
                last_progress = time.monotonic()

            await asyncio.sleep(_POLL_SLEEP)

        else:
            # Timeout
            elapsed = int(time.monotonic() - start)
            _log(f"TIMEOUT tras {elapsed}s — matando worker")
            try:
                proc.kill()
            except Exception:
                pass
            try:
                params_file.unlink()
            except Exception:
                pass
            result["error"] = f"Timeout: el scraping no terminó en {int(total_timeout)}s"
            return result

        # ── Clean up params ───────────────────────────────────────────
        try:
            params_file.unlink()
        except Exception:
            pass

        # ── Read result ───────────────────────────────────────────────
        if result_file.exists():
            try:
                res_data = json.loads(result_file.read_text("utf-8"))
                result.update(res_data)
                rc = result.get("record_count", 0)
                nf = len(result.get("files_written", []))
                elapsed = int(time.monotonic() - start)
                _log(f"Worker {job_id} OK ({elapsed}s): {rc} registros, {nf} archivos")
                try:
                    result_file.unlink()
                except Exception:
                    pass
            except Exception as e:
                result["error"] = f"Error leyendo resultado: {e}"
                _log(f"Error leyendo resultado: {e}")
        else:
            result["error"] = (
                "El worker terminó sin generar resultado. "
                "Probablemente Chromium no pudo conectarse. Intenta de nuevo."
            )
            _log(f"Worker {job_id}: sin archivo de resultado")

        return result
