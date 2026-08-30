-- homelib schema. Implements specs/indexing.md (which owns this DDL) and the
-- query_log additions in specs/monitoring.md.
--
-- Runs once, on an empty data volume, via the postgres image's
-- docker-entrypoint-initdb.d hook. Everything is IF NOT EXISTS so a re-run
-- against an existing volume is a no-op rather than an error.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS books (
    book_id      text PRIMARY KEY,
    title        text NOT NULL,
    authors      text[] NOT NULL DEFAULT '{}',
    language     text NOT NULL DEFAULT 'en',
    source_url   text NOT NULL DEFAULT '',
    license_note text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS blocks (
    block_id     text PRIMARY KEY,
    book_id      text NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
    ordinal      int  NOT NULL,
    section_path text[] NOT NULL DEFAULT '{}',
    text         text NOT NULL,
    char_start   int  NOT NULL,
    char_end     int  NOT NULL,
    -- Flattened Provenance (see specs/core-models.md). Kept inline rather than
    -- in a side table: every citation needs it, so a join would be on the hot path.
    format       text NOT NULL,
    page         int,
    spine_index  int,
    anchor       text
);
CREATE INDEX IF NOT EXISTS ix_blocks_book_ordinal ON blocks (book_id, ordinal);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id     text PRIMARY KEY,
    book_id      text NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
    block_ids    text[] NOT NULL,
    section_path text[] NOT NULL DEFAULT '{}',
    text         text NOT NULL,
    char_start   int  NOT NULL,
    char_end     int  NOT NULL,
    tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX IF NOT EXISTS ix_chunks_tsv ON chunks USING GIN (tsv);
CREATE INDEX IF NOT EXISTS ix_chunks_book ON chunks (book_id);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id  text PRIMARY KEY REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL   -- all-MiniLM-L6-v2
);
-- The ivfflat index is created by 03-index.sql AFTER ingestion: ivfflat needs
-- rows present to build meaningful centroids, and building it on an empty
-- table produces an index that silently degrades recall.

CREATE TABLE IF NOT EXISTS catalog (
    ol_key             text PRIMARY KEY,
    title              text NOT NULL,
    authors            text[] NOT NULL DEFAULT '{}',
    subjects           text[] NOT NULL DEFAULT '{}',
    first_publish_year int,
    description        text,
    provenance_note    text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_catalog_subjects ON catalog USING GIN (subjects);

CREATE TABLE IF NOT EXISTS query_log (
    request_id          text PRIMARY KEY,
    ts                  timestamptz NOT NULL DEFAULT now(),
    latency_ms          int  NOT NULL,
    arm                 text NOT NULL,
    k                   int  NOT NULL,
    rerank              boolean NOT NULL DEFAULT false,
    rewrite             boolean NOT NULL DEFAULT false,
    model               text NOT NULL DEFAULT '',
    tokens_prompt       int  NOT NULL DEFAULT 0,
    tokens_completion   int  NOT NULL DEFAULT 0,
    -- Privacy default: only a 16-char sha256 prefix of the query is stored.
    -- Plaintext is opt-in and NULL unless the caller explicitly asked for it.
    query_sha256_prefix text NOT NULL,
    query_plaintext     text,
    degraded            boolean NOT NULL DEFAULT false,
    feedback            text CHECK (feedback IN ('up', 'down'))
);
CREATE INDEX IF NOT EXISTS ix_query_log_ts ON query_log (ts DESC);
