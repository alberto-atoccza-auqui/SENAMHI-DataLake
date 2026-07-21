"""SENAMHI scraper engine — zendriver-based web scraper.

This sub-package is a self-contained copy of the original CLI scraper,
adapted to run as an async library inside the FastAPI application.

Public API
----------
ScraperEngine.run(station_data, mode_params, *, output_dir, csv_separator, csv_encoding)
    Executes the scraping and saves CSV files.  Returns a dict with
    ``file_generated``, ``record_count``, ``skipped`` (bool), and ``options_count``.
"""
from .engine import ScraperEngine

__all__ = ["ScraperEngine"]
