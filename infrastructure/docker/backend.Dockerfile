FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Install system dependencies (libpq, libmagic for MIME inspection, clamdscan, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    curl \
    clamdscan \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged system user and group
RUN groupadd --system --gid 10001 docuspace \
    && useradd --system --uid 10001 --gid docuspace --home-dir /app --shell /usr/sbin/nologin docuspace

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

COPY backend/ /app/backend/

RUN mkdir -p /tmp/docuspace/quarantine \
    && chown -R docuspace:docuspace /app /tmp/docuspace

EXPOSE 8000

WORKDIR /app/backend
USER docuspace

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
