FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_LOG_DIR=/app/logs

WORKDIR /app

RUN apt-get update \
 && apt-get -y upgrade \
 && apt-get install -y --no-install-recommends ca-certificates curl wget tini \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 appuser \
 && mkdir -p /app/logs /app/static/uploads \
 && chown -R appuser:appuser /app

COPY --chown=appuser:appuser requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=appuser:appuser . /app

COPY --chown=appuser:appuser entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

USER appuser
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/entrypoint.sh"]
