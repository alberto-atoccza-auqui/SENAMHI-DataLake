"""Standalone scraper worker — runs zendriver in its OWN process.

This script is invoked as a subprocess by ScraperEngine so that
zendriver (and Chromium) run in a clean process with their own
asyncio event loop, completely isolated from uvicorn's event loop.

Usage (internal — called by engine.py):
    python scraper_worker.py <params_json_file> <result_json_file>

Exit codes:
    0  success (result written to result_json_file)
    1  fatal error (result written to result_json_file with 'error' key)
"""
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

# ---------------------------------------------------------------------------
# Inline copies of the utilities (no relative imports — this is __main__)
# ---------------------------------------------------------------------------

from bs4 import BeautifulSoup

_HTML_PARSER = "html.parser"

BASE_URL = "https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"

HEADERS_METEOROLOGICAL_AUTO = [
    "Año", "Mes", "Día", "Hora",
    "Temperatura (°C)", "Humedad Relativa (%)", "Precipitación (mm)",
    "Velocidad del Viento (m/s)", "Dirección del Viento (°)",
    "Radiación Solar (W/m²)", "Presión Atmosférica (hPa)",
]
HEADERS_METEOROLOGICAL_CONV = [
    "Año", "Mes", "Día",
    "Temperatura Máxima (°C)", "Temperatura Mínima (°C)",
    "Temperatura Media (°C)", "Humedad Relativa Máxima (%)",
    "Humedad Relativa Mínima (%)", "Humedad Relativa Media (%)",
    "Precipitación (mm)", "Evaporación (mm)",
    "Horas de Sol (h)", "Velocidad del Viento (m/s)",
]
HEADERS_HYDROLOGICAL = [
    "Año", "Mes", "Día",
    "Nivel de Agua (m)", "Caudal (m³/s)",
]


def get_headers(station_type: str, status: str) -> List[str]:
    if station_type == "H":
        return HEADERS_HYDROLOGICAL
    if status == "AUTOMATICA":
        return HEADERS_METEOROLOGICAL_AUTO
    return HEADERS_METEOROLOGICAL_CONV


def build_url(station_data: Dict) -> str:
    params = {
        "cod": station_data["code"],
        "estado": station_data["status"],
        "tipo_esta": station_data["station_type"],
        "cate": station_data["category"],
        "cod_old": station_data.get("legacy_code", ""),
    }
    return f"{BASE_URL}?{urlencode(params)}"


def extract_select_options(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, _HTML_PARSER)
    sel = soup.find("select")
    if not sel:
        return []
    return [
        {
            "value": opt.get("value", ""),
            "text": opt.get_text(strip=True),
        }
        for opt in sel.find_all("option")
    ]


def parse_date(s: str):
    m = re.match(r"^(\d{4})[-/](\d{2})[-/](\d{2})$", s.strip())
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return (y, mo, d) if (1 <= mo <= 12 and 1 <= d <= 31) else None


def table_to_csv(html: str, separator: str, start_line: int) -> str:
    soup = BeautifulSoup(html, _HTML_PARSER)
    table = soup.find("table")
    if not table:
        return ""
    lines = []
    for ri, row in enumerate(table.find_all("tr")):
        if start_line and ri < start_line:
            continue
        cells = row.find_all(["td", "th"])
        row_data = []
        for ci, cell in enumerate(cells):
            txt = re.sub(r"\s+", " ", cell.get_text(strip=True))
            if separator in txt:
                txt = f'"{txt}"'
            if ri > 0 and ci == 0:
                parsed = parse_date(txt)
                if parsed is None:
                    row_data = None
                    break
                row_data.extend([f"{parsed[0]:04d}", f"{parsed[1]:02d}", f"{parsed[2]:02d}"])
            else:
                row_data.append("0.0" if txt == "S/D" else txt)
        if row_data and any(c.strip() for c in row_data):
            lines.append(separator.join(row_data))
    return "\n".join(lines)


def filter_options(opts, mode, year, month, end_year):
    valid = [o for o in opts if re.match(r"^\d{6}$", o["value"].strip())]
    if mode == "month":
        target = f"{year:04d}{month:02d}"
        return [o for o in valid if o["value"] == target]
    if mode == "year":
        return [o for o in valid if o["value"].startswith(str(year))]
    if mode == "period":
        ey = end_year or year
        return [o for o in valid if year <= int(o["value"][:4]) <= ey]
    return valid


def write_csv(filepath: Path, headers, table_html, sep, enc, start_line) -> int:
    body = table_to_csv(table_html, sep, start_line)
    if not body:
        return 0
    lines = [ln for ln in body.splitlines() if ln.strip()]
    if not lines:
        return 0
    filepath.parent.mkdir(parents=True, exist_ok=True)
    write_header = not filepath.exists()
    with open(filepath, "a", encoding=enc, newline="") as f:
        if write_header:
            f.write(sep.join(headers) + "\n")
        f.write("\n".join(lines) + "\n")
    return len(lines)


def log(log_path: Path, msg: str):
    import datetime
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [worker] {msg}\n")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Main scraping coroutine
# ---------------------------------------------------------------------------

async def scrape(params: Dict, log_path: Path) -> Dict:
    import zendriver as zd
    from zendriver import Config as ZdConfig

    station_data = params["station_data"]
    mode_params = params["mode_params"]
    output_dir = params["output_dir"]
    sep = params.get("csv_separator", ";")
    enc = params.get("csv_encoding", "utf-8")
    timeout = params.get("timeout_seconds", 45.0)
    poll = params.get("poll_interval", 0.5)

    station_name = station_data.get("name", station_data["code"]).replace(" ", "")
    station_type = station_data.get("station_type", "M")
    status = station_data.get("status", "DIFERIDO")
    headers = get_headers(station_type, status)
    start_line = 1 if status == "AUTOMATICA" else 2

    mode = mode_params["mode"]
    year = mode_params["year"]
    month = mode_params.get("month")
    end_year = mode_params.get("end_year")
    consolidated = mode_params.get("consolidated", True)

    csv_root = Path(output_dir) / station_name
    csv_root.mkdir(parents=True, exist_ok=True)
    url = build_url(station_data)

    log(log_path, f"URL: {url}")
    log(log_path, "Iniciando zendriver con Config(no_sandbox=True, timeout=3.0, tries=90)...")

    browser = None
    MAX_BROWSER_RETRIES = 3
    last_browser_error = ""
    for retry in range(1, MAX_BROWSER_RETRIES + 1):
        try:
            cfg = ZdConfig(
                no_sandbox=True,
                browser_connection_timeout=3.0,
                browser_connection_max_tries=90,
            )
            browser = await zd.start(cfg)
            log(log_path, f"Browser iniciado OK (intento {retry})")
            break
        except Exception as e:
            last_browser_error = str(e)
            log(log_path, f"Intento {retry}/{MAX_BROWSER_RETRIES} de browser fallido: {last_browser_error[:200]}")
            if retry < MAX_BROWSER_RETRIES:
                await asyncio.sleep(5)
                continue
    
    if browser is None:
        return {
            "file_generated": "", "record_count": 0,
            "skipped": False, "options_count": 0,
            "files_written": [],
            "error": f"No se pudo conectar al navegador tras {MAX_BROWSER_RETRIES} intentos: {last_browser_error}",
        }

    result = {
        "file_generated": "", "record_count": 0,
        "skipped": False, "options_count": 0,
        "files_written": [], "error": "",
    }

    try:
        page = await browser.get(url)
        log(log_path, "Pagina cargada")

        tab = await page.wait_for(selector="a#tabla-tab", timeout=timeout)
        if not tab:
            result["error"] = "Pestana #tabla-tab no encontrada"
            return result
        await tab.click()
        log(log_path, "Tab clickeada")

        iframe = await page.wait_for(selector="iframe#contenedor", timeout=timeout)
        if not iframe:
            result["error"] = "iframe#contenedor no encontrado"
            return result

        # Wait for initial table
        elapsed = 0.0
        table_found = None
        while elapsed < timeout:
            table_found = await iframe.query_selector("table#dataTable")
            if table_found:
                break
            await asyncio.sleep(poll)
            elapsed += poll
        if not table_found:
            result["error"] = "table#dataTable no cargo en iframe"
            return result
        log(log_path, "Tabla inicial encontrada")

        select_el = await page.wait_for(selector="select#CBOFiltro", timeout=timeout)
        if not select_el:
            result["error"] = "select#CBOFiltro no encontrado"
            return result
        select_html = await select_el.get_html()
        all_opts = extract_select_options(select_html)
        filtered = filter_options(all_opts, mode, year, month, end_year)
        result["options_count"] = len(filtered)
        log(log_path, f"{len(filtered)} periodos para procesar")

        if not filtered:
            result["error"] = f"No hay periodos para modo={mode} year={year} month={month}"
            return result

        total_rows = 0
        files_written: List[str] = []
        initialized_files: set[str] = set()

        for i, opt in enumerate(filtered, 1):
            pv = opt["value"]
            log(log_path, f"[{i}/{len(filtered)}] Procesando periodo {pv}")

            opt_el = await page.query_selector(f"option[value='{pv}']")
            if not opt_el:
                log(log_path, f"  SKIP: option[value={pv}] no encontrado")
                continue
            await opt_el.select_option()
            await asyncio.sleep(2)

            elapsed2 = 0.0
            updated = None
            while elapsed2 < timeout:
                updated = await iframe.query_selector("table#dataTable")
                if updated:
                    break
                await asyncio.sleep(poll)
                elapsed2 += poll
            if not updated:
                log(log_path, f"  SKIP: tabla no actualizo para {pv}")
                continue

            table_html = await updated.get_html()

            if consolidated:
                if mode == "month":
                    fname = f"{station_name}-{pv}.csv"
                elif mode == "year":
                    fname = f"{station_name}-{year}.csv"
                else:
                    fname = f"{station_name}-{year}-{end_year or year}.csv"
            else:
                fname = f"{station_name}-{pv}.csv"
            fpath = csv_root / fname
            fpath_key = str(fpath)

            if fpath_key not in initialized_files:
                if fpath.exists():
                    fpath.unlink()
                initialized_files.add(fpath_key)

            rows = write_csv(fpath, headers, table_html, sep, enc, start_line)
            total_rows += rows
            if fpath_key not in files_written:
                files_written.append(fpath_key)
            log(log_path, f"  {rows} filas -> {fname}")

        result["record_count"] = total_rows
        result["files_written"] = files_written
        result["file_generated"] = files_written[0] if files_written else ""

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(log_path, f"EXCEPCION: {e}\n{tb}")
        result["error"] = f"{e}\n{tb}"
    finally:
        try:
            await asyncio.sleep(1)
            await browser.stop()
            log(log_path, "Browser cerrado")
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: scraper_worker.py <params.json> <result.json>")
        sys.exit(1)

    params_file = Path(sys.argv[1])
    result_file = Path(sys.argv[2])

    params = json.loads(params_file.read_text(encoding="utf-8"))

    log_path = Path(params["output_dir"]).parent / "logs" / "scraper.log"
    log(log_path, f"=== WORKER INICIADO pid={sys.argv} ===")

    try:
        result = asyncio.run(scrape(params, log_path))
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(log_path, f"WORKER FATAL: {e}\n{tb}")
        result = {"file_generated": "", "record_count": 0, "error": str(e),
                  "skipped": False, "options_count": 0, "files_written": []}

    result_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    log(log_path, f"=== WORKER FINALIZADO: {result.get('record_count',0)} registros ===")
    sys.exit(0 if not result.get("error") else 1)
