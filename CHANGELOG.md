# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.1.0] - Unreleased

### Added
- Queue-based extraction flow so the FastAPI app enqueues jobs instead of running zendriver inside the web process.
- Standalone worker CLI: `python scripts/run_extraction_worker.py`.
- Windows launcher: `start_senamhi.bat` to open API, worker and browser in one step.
- `clean_for_github.bat` to remove local runtime artifacts before publishing.
- `DELETE /api/extractions/tasks` to clear extraction history from the UI.

### Changed
- `POST /api/extractions` now creates queued tasks by default.
- Extraction status and recent task views now reflect database state only.
- CSV reuse is now exact per request instead of falling back to any CSV from the same station.
- Worker timeout is configurable through `SCRAPER_WORKER_TIMEOUT_SECONDS`.
- Runtime temp files, logs and pycache folders are treated as local-only artifacts.

### Fixed
- Prevented duplicate rows when a worker rewrites the same consolidated CSV.
- Removed stale references to local machine paths from docs and scripts.

## [2.0.0] - 2026-07-20

### Added
- Initial SaaS-style web platform for SENAMHI extraction and CSV browsing.
- FastAPI backend with SQLite/SQLAlchemy async stack.
- Vanilla JS SPA frontend with dashboard, stations, extraction, files and map views.
- Zendriver-based extraction engine isolated behind a worker process.

