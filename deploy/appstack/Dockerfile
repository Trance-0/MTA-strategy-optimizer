# syntax=docker/dockerfile:1.7

ARG BUILD_COMMIT=unknown

# Build the unchanged Vue client first. The Flask image receives only its
# static output; Node and npm do not exist in the runtime layer.
FROM node:22.23.0-bookworm-slim AS client
ARG BUILD_COMMIT
ENV BUILD_COMMIT=${BUILD_COMMIT}
WORKDIR /workspace/dashboard
COPY VERSION /workspace/VERSION
COPY dashboard/package.json dashboard/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY dashboard/ ./
RUN npm run build

# Install the locked Python environment independently so source-only edits do
# not invalidate the dependency layer.
FROM python:3.12.11-slim-bookworm AS runtime
ARG BUILD_COMMIT
COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROJECT_COMMIT=${BUILD_COMMIT} \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /application
COPY pyproject.toml uv.lock ./
COPY VERSION ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra backend --extra strategy-evaluation --no-dev --no-install-project

COPY backend/ backend/
COPY dashboard/config.py dashboard/models.py dashboard/
COPY modules/ modules/
COPY script/ script/
COPY --from=client /workspace/dashboard/dist dashboard/dist/

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin app \
    && chown -R app:app /application

USER 10001:10001
EXPOSE 8501

CMD ["gunicorn", "--bind", "0.0.0.0:8501", "--workers", "1", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "backend.wsgi:application"]
