FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    APP_LOG_DIR=/app/logs

WORKDIR /app

RUN apt-get update \
 && apt-get -y upgrade \
 && apt-get install -y --no-install-recommends ca-certificates curl wget tini build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 appuser \
 && mkdir -p /app/logs /app/public \
 && chown -R appuser:appuser /app

# src 레이아웃(packages.find where=["src"])이라 빌드 시 소스가 있어야 한다 → 전체 복사 후 설치.
COPY --chown=appuser:appuser . /app
RUN pip install --upgrade pip \
 && pip install --no-cache-dir .

EXPOSE 8080

USER appuser
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
