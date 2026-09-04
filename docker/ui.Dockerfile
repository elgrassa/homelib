# homelib Streamlit UI. Deliberately thin: it holds no database driver and no
# retrieval code, because the UI talks only through the public API (specs/ui.md).
FROM python:3.13-slim-bookworm

# UV_NO_CACHE: uv's download cache is worth ~1.4 GB inside the dependency
# layer and is never read again at runtime. Layers are immutable, so
# deleting it in a later step would not shrink the image — it must never
# be written in the first place.
# PYTHONPATH=/app: Streamlit runs apps/ui/app.py as a script, so `import apps`
# fails unless /app is on sys.path. Pytest gets the same via pythonpath=["."].
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/homelib-core/pyproject.toml packages/homelib-core/
COPY packages/homelib-rag/pyproject.toml packages/homelib-rag/
RUN mkdir -p packages/homelib-core/src/homelib_core packages/homelib-rag/src/homelib_rag \
    && touch packages/homelib-core/src/homelib_core/__init__.py \
             packages/homelib-rag/src/homelib_rag/__init__.py \
    && uv sync --frozen --no-dev

COPY packages/ packages/
COPY apps/ apps/
RUN uv sync --frozen --no-dev

EXPOSE 8501
HEALTHCHECK --interval=10s --timeout=5s --retries=10 \
    CMD curl -fs http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "apps/ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
