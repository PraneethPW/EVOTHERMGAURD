# Railway builds from the repository root; the FastAPI service lives in /backend.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY backend/requirements-production.txt ./requirements.txt
ARG RUNTIME_REQUIREMENTS_REV=2
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
RUN mkdir -p /app/storage /app/backend/storage

# Railway overrides PORT when it provides one; 8080 matches its Docker healthcheck fallback.
EXPOSE 8080
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"
