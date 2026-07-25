# BilimUz Backend — production image
# Multi-stage build: dependencies compiled in one layer, final image stays slim.

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed to build psycopg2 (not psycopg2-binary would need more,
# but we keep libpq-dev for compatibility if the binary wheel is unavailable
# on a given platform).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as a non-root user — never run the app as root in production.
RUN useradd --create-home --shell /bin/bash bilimuz \
    && chown -R bilimuz:bilimuz /app
USER bilimuz

EXPOSE 8000

# No --reload in production; docker-compose.yml overrides this command for
# local dev (see the `command:` override there).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
