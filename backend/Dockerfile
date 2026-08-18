# CareerPilot AI backend image
# NOTE: Playwright browsers are NOT installed in Phase 1 (no automation yet).
# They will be added to this image in Phase 9 (Application Assistant).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Data directory (uploads / sqlite fallback) — override with a volume in prod
RUN mkdir -p /data/uploads
ENV DATABASE_URL=postgresql+psycopg://careerpilot:careerpilot@db:5432/careerpilot
ENV AUTO_CREATE_TABLES=false

EXPOSE 8000

# Run migrations, then start the API. Use `alembic upgrade head` before start.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
