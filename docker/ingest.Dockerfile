# One-shot dlt ingestion job: snapshot + catalog -> Postgres, embeddings at load.
# Shares the API image's model cache strategy so seeding never hits the network.
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/opt/models \
    SENTENCE_TRANSFORMERS_HOME=/opt/models

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates djvulibre-bin \
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

RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY packages/ packages/
COPY apps/ apps/
RUN uv sync --frozen --no-dev

CMD ["python", "-m", "apps.ingest.pipeline"]
