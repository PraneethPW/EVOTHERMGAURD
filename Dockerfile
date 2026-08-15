# Railway builds from the repository root; the FastAPI service lives in /backend.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements-production.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
RUN mkdir -p /app/storage /app/backend/storage

# Railway provides PORT at runtime. Shell form expands it safely with a local fallback.
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
