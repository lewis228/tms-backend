FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    APP_LOG_DIR=/app/logs

WORKDIR /app

RUN apt-get update \
 && apt-get -y upgrade \
 && apt-get install -y --no-install-recommends ca-certificates curl wget tini build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 appuser \
 && mkdir -p /app/logs \
 && chown -R appuser:appuser /app

COPY --chown=appuser:appuser pyproject.toml /app/pyproject.toml
RUN pip install --upgrade pip \
 && pip install --no-cache-dir .

COPY --chown=appuser:appuser . /app

EXPOSE 8080

USER appuser
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
