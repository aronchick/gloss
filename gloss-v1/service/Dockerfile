FROM ghcr.io/astral-sh/uv:0.8.4@sha256:46968e602e1de60a6511cb090ba3945ea8fd9c2e3e321a66111b01baf0cb5ff8 AS uv
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY gloss_service ./gloss_service
COPY --from=schemas generation-profile.schema.json environment-attestation.schema.json control-handoff.schema.json /opt/gloss/schemas/
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/gloss/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin gloss \
    && mkdir -p /app /data \
    && chown -R gloss:gloss /app /data

COPY --from=builder /build/.venv /opt/gloss/venv
COPY --from=builder /opt/gloss/schemas /opt/gloss/schemas
WORKDIR /app
COPY alembic.ini ./
COPY alembic ./alembic

FROM runtime-base AS api
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail http://127.0.0.1:8000/health/live || exit 1
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn gloss_service.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*"]

FROM runtime-base AS worker
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*
USER 10001:10001
CMD ["gloss-worker"]

# Built only after the canonical grader image has been pinned locally. This is
# the sole image that receives and parses the original upload.
FROM gloss/grader:1.0.0 AS quarantine-job
USER root
COPY . /opt/gloss/service
RUN /bin/uv export --project /opt/gloss/service --frozen --no-dev --no-emit-project \
      --format requirements-txt --output-file /tmp/service-requirements.txt \
    && /bin/uv pip install --python /opt/gloss/venv/bin/python \
      --requirements /tmp/service-requirements.txt \
    && /bin/uv pip install --python /opt/gloss/venv/bin/python \
      --no-deps /opt/gloss/service \
    && rm /tmp/service-requirements.txt
# The grader image freezes wall time for deterministic rendering. Quarantine
# verdicts are short-lived security credentials and must use real wall time.
ENV LD_PRELOAD="" \
    FAKETIME="" \
    FAKETIME_DONT_FAKE_MONOTONIC="" \
    FAKETIME_NO_CACHE=""
USER grader
ENTRYPOINT ["python3", "-m", "gloss_service.quarantine_job"]
