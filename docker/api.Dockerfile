# homelib API image.
#
# Build context is the repo root (see docker-compose.yml), because the API
# depends on the two workspace packages and uv needs the whole workspace to
# resolve them.
FROM python:3.13-slim-bookworm

# UV_NO_CACHE: uv's download cache is worth ~1.4 GB inside the dependency
# layer and is never read again at runtime. Layers are immutable, so
# deleting it in a later step would not shrink the image — it must never
# be written in the first place.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    # Keep the embedding model inside the image, not in a runtime download:
    # a reviewer on a slow link should not wait for HuggingFace on first query.
    HF_HOME=/opt/models \
    SENTENCE_TRANSFORMERS_HOME=/opt/models

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer: only the manifests, so a source edit does not re-resolve.
COPY pyproject.toml uv.lock ./
COPY packages/homelib-core/pyproject.toml packages/homelib-core/
COPY packages/homelib-rag/pyproject.toml packages/homelib-rag/
RUN mkdir -p packages/homelib-core/src/homelib_core packages/homelib-rag/src/homelib_rag \
    && touch packages/homelib-core/src/homelib_core/__init__.py \
             packages/homelib-rag/src/homelib_rag/__init__.py \
    && uv sync --frozen --no-dev

# Bake the embedding weights in. all-MiniLM-L6-v2 is ~90 MB — worth the image
# size to make `docker compose up` self-contained and offline-capable.
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY packages/ packages/
COPY apps/ apps/
COPY evals/ evals/
RUN uv sync --frozen --no-dev

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=30s \
    CMD curl -fs http://localhost:8000/health || exit 1

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
