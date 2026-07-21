<div align="center">

# SENAMHI DataLake

Plataforma web para extracción, gestión y visualización de datos meteorológicos e hidrológicos del SENAMHI Perú.

</div>

---

## Qué incluye

- Dashboard con métricas de estaciones y extracciones
- Catálogo de estaciones con filtros
- Extracción por mes, año o periodo
- Historial de tareas y archivos CSV
- Visualización de datos y mapa
- Worker separado para ejecutar zendriver fuera del proceso web

## Cómo arrancar

### Opción recomendada en Windows

```bash
start_senamhi.bat
```

Ese launcher abre la API, el worker de cola y la página en el navegador.

### Arranque manual

```bash
python run_dev.py
python scripts/run_extraction_worker.py
```

Para procesar una sola tarea pendiente y salir:

```bash
python scripts/run_extraction_worker.py --once
```

## Endpoints clave

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/extractions` | Encola una extracción |
| `GET` | `/api/extractions/status` | Estado global de tareas |
| `GET` | `/api/extractions/tasks` | Historial de extracciones |
| `DELETE` | `/api/extractions/tasks` | Limpia historial completado/fallido |
| `GET` | `/api/files` | Lista archivos CSV |
| `DELETE` | `/api/files/{station}/{file}` | Elimina un CSV |

## Limpieza antes de GitHub

```bash
clean_for_github.bat
```

Eso borra temporales locales, logs y cachés generados por desarrollo.

## Estructura

```text
src/senamhi_datalake/   Backend FastAPI + servicios
web/                    Frontend SPA
scripts/                Worker de cola
data/                   Catálogo y base local
output/                 Archivos generados localmente
```

