# Contributing to SENAMHI DataLake

Thanks for helping improve the project.

## Development setup

```bash
git clone https://github.com/senamhi-datalake/senamhi-datalake.git
cd senamhi-datalake
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,scraper]"
```

## Run locally

```bash
python run_dev.py
python scripts/run_extraction_worker.py
```

On Windows, `start_senamhi.bat` opens the API, worker and browser in one step.

## Before opening a pull request

1. Run `python -m compileall -q src scripts`.
2. Run `node --check web\js\app.js`.
3. Run the test suite with `pytest`.
4. Verify `clean_for_github.bat` leaves no runtime artifacts in `output\tmp` or `output\logs`.
5. Update `CHANGELOG.md` for user-visible changes.

## Project layout

```text
src/senamhi_datalake/   Python package
web/                    SPA frontend
scripts/                Developer and worker utilities
data/                   Station catalog and local database
tests/                  Automated tests
```

## Style

- Keep changes focused.
- Prefer the existing FastAPI, SQLAlchemy and vanilla JS patterns.
- Avoid hard-coded local paths.
- Add tests when behavior changes.

