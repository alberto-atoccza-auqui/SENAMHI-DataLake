# SENAMHI DataLake production image
# The web app runs FastAPI; extraction is handled by a separate worker process.

FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ src/
COPY web/ web/
COPY data/ data/
COPY scripts/ scripts/

RUN pip install --no-cache-dir -e ".[scraper]"

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMIUM_FLAGS="--no-sandbox --headless --disable-gpu"

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

EXPOSE 8000

CMD ["uvicorn", "senamhi_datalake.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
