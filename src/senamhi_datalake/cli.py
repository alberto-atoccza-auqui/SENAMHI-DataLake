"""Command-line helpers for SENAMHI DataLake."""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from .core.config import settings
from .core.database import async_session_factory
from .models.orm import ExtractionTask, TaskStatus
from .services.task_executor import execute_extraction_task


async def _next_pending_task_id() -> int | None:
    async with async_session_factory() as db:
        task = (
            await db.execute(
                select(ExtractionTask)
                .where(ExtractionTask.status == TaskStatus.PENDING.value)
                .order_by(ExtractionTask.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return task.id if task else None


async def _run_extraction_worker(*, once: bool, poll_seconds: float) -> int:
    print(f"Queue worker using DB: {settings.database_url}")
    print("Press Ctrl+C to stop.")

    processed = 0
    while True:
        task_id = await _next_pending_task_id()
        if task_id is None:
            if once:
                print("No pending extraction tasks.")
                return 0 if processed else 2
            await asyncio.sleep(poll_seconds)
            continue

        print(f"Processing extraction task #{task_id}...")
        await execute_extraction_task(task_id)
        processed += 1

        if once:
            return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one pending extraction task and exit.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=5.0,
        help="Seconds to wait between queue checks.",
    )
    args = parser.parse_args()

    try:
        return asyncio.run(
            _run_extraction_worker(
                once=args.once,
                poll_seconds=args.poll_seconds,
            )
        )
    except KeyboardInterrupt:
        print("\nWorker stopped.")
        return 130
