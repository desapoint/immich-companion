# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build


FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY backend/pyproject.toml /build/backend/pyproject.toml
COPY backend/companion /build/backend/companion
RUN pip install /build/backend


FROM builder AS test

COPY backend/tests /build/backend/tests
COPY tools/generate_test_media.py /build/tools/generate_test_media.py
RUN pip install "/build/backend[dev]"
WORKDIR /build/backend
RUN pytest && ruff check companion tests


FROM python:3.12-slim AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COMPANION_ENV=production \
    COMPANION_FRONTEND_DIR=/opt/immich-companion/frontend \
    ALLOW_DESTRUCTIVE_ACTIONS=false

RUN groupadd --gid "$APP_GID" companion \
    && useradd --uid "$APP_UID" --gid "$APP_GID" --no-create-home --shell /usr/sbin/nologin companion

COPY --from=builder /opt/venv /opt/venv
COPY --from=frontend-builder --chown=companion:companion /build/frontend/dist /opt/immich-companion/frontend

USER companion
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/live', timeout=2)"]

CMD ["uvicorn", "companion.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
