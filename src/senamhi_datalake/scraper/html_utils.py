"""HTML utility functions for the SENAMHI scraper.

Adapted from the original senamhi-scraper/src/html_utils.py.
All settings references have been replaced with explicit parameters
so this module has zero dependency on the original project.
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

_HTML_PARSER = "html.parser"


# ── Select options ────────────────────────────────────────────────────


def extract_select_options(html_content: str) -> List[dict]:
    """Extract value/text pairs from the first <select> in *html_content*.

    Returns a list of dicts with keys ``value``, ``text``, ``selected``,
    ``disabled``.
    """
    soup = BeautifulSoup(html_content, _HTML_PARSER)
    select_element = soup.find("select")
    if not select_element:
        return []

    result: List[dict] = []
    for option in select_element.find_all("option"):
        result.append(
            {
                "value": option.get("value", ""),
                "text": option.get_text(strip=True),
                "selected": option.has_attr("selected"),
                "disabled": option.has_attr("disabled"),
            }
        )
    return result


# ── Date helpers ──────────────────────────────────────────────────────


def _parse_date(date_str: str) -> Optional[tuple]:
    """Return (year, month, day) ints if *date_str* matches YYYY-MM-DD or YYYY/MM/DD."""
    m = re.match(r"^(\d{4})[-/](\d{2})[-/](\d{2})$", date_str.strip())
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= month <= 12 and 1 <= day <= 31:
        return year, month, day
    return None


# ── Table → CSV ───────────────────────────────────────────────────────


def _process_row(row, row_index: int, separator: str) -> Optional[List[str]]:
    """Convert one <tr> into a list of strings.

    For data rows (row_index > 0) the first cell must be a valid date;
    it is expanded into three columns: year, month, day.
    Cells with the placeholder "S/D" are converted to "0.0".
    Returns None if the row should be skipped.
    """
    cells = row.find_all(["td", "th"])
    row_data: List[str] = []

    for cell_idx, cell in enumerate(cells):
        cell_text = re.sub(r"\s+", " ", cell.get_text(strip=True))
        if separator in cell_text:
            cell_text = f'"{cell_text}"'

        if row_index > 0 and cell_idx == 0:
            parsed = _parse_date(cell_text)
            if parsed is None:
                return None  # skip rows with invalid dates
            y, mo, d = parsed
            row_data.extend([f"{y:04d}", f"{mo:02d}", f"{d:02d}"])
        else:
            row_data.append("0.0" if cell_text == "S/D" else cell_text)

    return row_data if row_data and any(c.strip() for c in row_data) else None


def html_table_to_csv(
    html_content: str,
    *,
    separator: str = ";",
    start_line: int = 0,
) -> str:
    """Convert the first <table> in *html_content* to a CSV string.

    Parameters
    ----------
    html_content:
        Raw HTML that contains a ``<table>``.
    separator:
        Column delimiter (default ``";"``).
    start_line:
        Number of leading rows to skip (e.g. 1 for stations whose first
        HTML row is a sub-header rather than the real header).

    Returns an empty string if no table is found.
    """
    soup = BeautifulSoup(html_content, _HTML_PARSER)
    table = soup.find("table")
    if not table:
        return ""

    csv_lines: List[str] = []
    for row_index, row in enumerate(table.find_all("tr")):
        if start_line and row_index < start_line:
            continue
        row_data = _process_row(row, row_index, separator)
        if row_data:
            csv_lines.append(separator.join(row_data))

    return "\n".join(csv_lines)
