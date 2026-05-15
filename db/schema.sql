-- AUA-Veritas SQLite Schema v2
-- Single-user, local-only. All data stays on this machine.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=OFF;  -- relaxed for MVP: no FK cascade needed

-- ── Users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY DEFAULT 'local',
    created_at  REAL NOT NULL DEFAULT (unixepoch('now')),
    settings    TEXT DEFAULT '{}'
);

-- ── Conversations ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL DEFAULT 'local',
    title           TEXT,
    created_at      REAL NOT NULL DEFAULT (unixepoch('now')),
    updated_at      REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_conv_user    ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC);

-- ── Messages ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    message_id      TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    callout_type    TEXT,
    models_used     TEXT,
    accuracy_level  TEXT,
    confidence      TEXT,
    created_at      REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);

-- ── Model Runs ────────────────────────────────────────────────────────────────
-- One row per model per query.
CREATE TABLE IF NOT EXISTS model_runs (
    run_id              TEXT PRIMARY KEY,
    query_id            TEXT,           -- loose reference, no FK constraint
    model_id            TEXT NOT NULL,
    round               TEXT NOT NULL DEFAULT 'answer',
    raw_response        TEXT,
    utility_score       REAL,
    confidence_score    REAL,
    vcg_welfare_score   REAL,
    vcg_winner          INTEGER DEFAULT 0,
    corrections_applied TEXT,
    latency_ms          REAL,
    created_at          REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_run_model ON model_runs(model_id);

-- ── Corrections ───────────────────────────────────────────────────────────────
-- Per-user correction memory. Matches memory_extractor.ExtractionResult.
CREATE TABLE IF NOT EXISTS corrections (
    correction_id           TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL DEFAULT 'local',
    model_id                TEXT,
    type                    TEXT,    -- factual_correction | persistent_instruction | etc.
    scope                   TEXT,    -- global | project | conversation | superseded
    corrective_instruction  TEXT,    -- injected into future prompts
    reason                  TEXT,
    canonical_query         TEXT NOT NULL DEFAULT 'general',
    domain                  TEXT NOT NULL DEFAULT 'general',
    confidence              REAL DEFAULT 0.9,
    decay_class             TEXT DEFAULT 'A',
    score_delta             INTEGER DEFAULT 0,
    query_preview           TEXT,
    extracted_via           TEXT DEFAULT 'rules',
    active_project          TEXT,
    pinned                  INTEGER DEFAULT 0,
    created_at              REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_corr_user    ON corrections(user_id);
CREATE INDEX IF NOT EXISTS idx_corr_canonical ON corrections(canonical_query);
CREATE INDEX IF NOT EXISTS idx_corr_domain  ON corrections(domain);
CREATE INDEX IF NOT EXISTS idx_corr_scope   ON corrections(scope);

-- ── Audit Log ─────────────────────────────────────────────────────────────────
-- Score events for Look Under the Hood graphs.
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id            TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL DEFAULT 'local',
    model_id            TEXT,
    event_type          TEXT NOT NULL,
    score_before        INTEGER,
    score_after         INTEGER,
    verdict             TEXT,
    correction_stored   INTEGER DEFAULT 0,
    query_preview       TEXT,
    correction_type     TEXT,
    payload             TEXT,    -- JSON catch-all for extra fields
    created_at          REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_model  ON audit_log(model_id);
CREATE INDEX IF NOT EXISTS idx_audit_event  ON audit_log(event_type);

-- ── Projects ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    project_id  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'local',
    name        TEXT NOT NULL,
    created_at  REAL NOT NULL DEFAULT (unixepoch('now'))
);
