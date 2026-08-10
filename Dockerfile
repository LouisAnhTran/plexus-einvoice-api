# syntax=docker/dockerfile:1

# ── build ────────────────────────────────────────────────────────────────────
# Dependencies are installed from uv.lock in a stage that is thrown away, so
# neither uv nor any build tooling ends up in the runtime image.
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Lockfile first, source second: editing a .py file then only re-runs the
# final COPY instead of reinstalling every dependency.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY . .

# ── runtime ──────────────────────────────────────────────────────────────────
FROM python:3.13-slim

# Non-root. A container that never needs to write outside /data has no reason
# to run as root.
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app \
    && mkdir -p /data \
    && chown app:app /data

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EINVOICE_DATABASE_PATH=":memory:"

USER app
EXPOSE 8100

# Kubernetes uses its own probes and ignores this; it's here so `docker run`
# and compose report health correctly. Uses stdlib rather than adding curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=4).status == 200 else 1)"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
