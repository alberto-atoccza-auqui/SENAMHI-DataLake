<div align="center">

# SENAMHI DataLake

Plataforma web para extracción, gestión y visualización de datos meteorológicos e hidrológicos del SENAMHI Perú.

</div>

---


## Sobre el proyecto

SENAMHI DataLake es una plataforma web para automatizar la extracción,
gestión y consulta de datos meteorológicos e hidrológicos del SENAMHI Perú.

El sistema integra un backend FastAPI, una interfaz web, una base de datos
local y un worker independiente para ejecutar procesos automatizados de
extracción mediante navegador.

---


## Capturas del sistema

### Dashboard
<img width="1835" height="932" alt="Captura de pantalla 2026-07-21 113514" src="https://github.com/user-attachments/assets/9ec5af35-7d78-4e4a-8a40-9c1f55f25d1f" />

### Catálogo de estaciones

<img width="1606" height="918" alt="Captura de pantalla 2026-07-21 114057" src="https://github.com/user-attachments/assets/f6a286b0-bcc2-4a5f-802f-4de4283a5c15" />

### Extracción e historial de tareas

<img width="840" height="620" alt="Captura de pantalla 2026-07-21 114226" src="https://github.com/user-attachments/assets/cc8db7b0-5148-4b44-8b71-027b33ea1335" />

### Arquitectura del sistema
<img width="900" alt="Arquitectura del sistema" src="https://github.com/user-attachments/assets/40d2b865-cb4c-4446-8685-4a8b00cf03f8" />

## Funcionalidades principales

- Dashboard con métricas de estaciones y extracciones
- Catálogo de estaciones con filtros
- Extracción por mes, año o periodo
- Historial de tareas y archivos CSV
- Visualización de datos y mapa
- Worker separado para ejecutar zendriver fuera del proceso web

## Tecnologías

- **Backend:** FastAPI + Python 3.11+
- **Frontend:** HTML, CSS y JavaScript
- **Base de datos:** SQLite + SQLAlchemy Async
- **Automatización:** Zendriver
- **Testing:** Pytest
- **CI/CD:** GitHub Actions

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

