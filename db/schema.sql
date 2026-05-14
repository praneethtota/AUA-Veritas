-- AUA-Veritas SQLite Schema
-- Single-user, local-only database.
-- All data stays on this machine unless the user explicitly exports it.

-- ── Users ─────────────────────────────────────────────────────────────────────
-- Single-user MVP: one row is created on first launch.
CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY DEFAULT 'local',
    created_at  REAL NOT NULL DEFAULT (unixepoch('now')),
    settings    TEXT DEFAULT '{}'    -- JSON blob for user preferences
);

-- ── API Keys ──────────────────────────────────────────────────────────────────
-- Stores which providers the user has connected.
-- Actual key values are stored in the OS keychain via keyring — NOT here.
CREATE TABLE IF NOT EXISTS connected_models (
    model_id        TEXT PRIMARY KEY,  -- e.g. "gpt-4o", "claude-sonnet-4-5"
    provider        TEXT NOT NULL,     -- "openai", "anthropic", "google", etc.
    display_name    TEXT NOT NULL,     -- "GPT-4o", "Claude Sonnet" etc.
    enabled         INTEGER DEFAULT 1, -- user can toggle on/off
    connected_at    REAL NOT NULL DEFAULT (unixepoch('now')),
    last_used_at    REAL
);

-- ── Conversations ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL DEFAULT 'local',
    title           TEXT,
    created_at      REAL NOT NULL DEFAULT (unixepoch('now')),
    updated_at      REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC);

-- ── Messages ──────────────────────────────────────────────────────────────────
-- raw_text stays local. Never uploaded.
CREATE TABLE IF NOT EXISTS messages (
    message_id      TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'callout')),
    content         TEXT NOT NULL,
    callout_type    TEXT,      -- NULL, 'correction', 'crosscheck', 'disagreement', 'highstakes'
    models_used     TEXT,      -- JSON array of model IDs that answered
    accuracy_level  TEXT,      -- 'fast', 'balanced', 'high', 'maximum'
    confidence      TEXT,      -- 'high', 'medium', 'uncertain'
    created_at      REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);

-- ── Query Records ─────────────────────────────────────────────────────────────
-- Canonical form for correction retrieval, mirrors AUA v0.6 spec.
CREATE TABLE IF NOT EXISTS query_records (
    query_id        TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL DEFAULT 'local',
    conversation_id TEXT REFERENCES conversations(conversation_id),
    message_id      TEXT REFERENCES messages(message_id),
    canonical_query TEXT NOT NULL,   -- deterministic key for correction retrieval
    domain          TEXT NOT NULL,   -- primary domain e.g. 'software_engineering'
    domain_dist     TEXT,            -- JSON: full probability distribution
    entities        TEXT,            -- JSON: extracted entities
    created_at      REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_qr_canonical ON query_records(canonical_query);
CREATE INDEX IF NOT EXISTS idx_qr_domain ON query_records(domain);

-- ── Model Runs ────────────────────────────────────────────────────────────────
-- One row per model per query (multiple rows for fanout/VCG).
CREATE TABLE IF NOT EXISTS model_runs (
    run_id              TEXT PRIMARY KEY,
    query_id            TEXT NOT NULL REFERENCES query_records(query_id),
    model_id            TEXT NOT NULL,   -- e.g. "gpt-4o"
    round               TEXT NOT NULL DEFAULT 'answer',  -- 'answer' | 'review'
    reviewing_run_id    TEXT,            -- for review round: which run_id is being reviewed
    raw_response        TEXT,            -- stays local
    utility_score       REAL,
    confidence_score    REAL,
    validation_status   TEXT,           -- 'pass' | 'fail' | 'uncertain'
    vcg_welfare_score   REAL,           -- W_i = P(domain) × confidence × prior_mean_U
    vcg_winner          INTEGER DEFAULT 0,
    corrections_applied TEXT,           -- JSON array of correction_ids injected
    latency_ms          REAL,
    created_at          REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_run_query ON model_runs(query_id);
CREATE INDEX IF NOT EXISTS idx_run_model ON model_runs(model_id);

-- ── Corrections ───────────────────────────────────────────────────────────────
-- Per-user correction memory. DPO-ready (rejected_run_id + chosen_text).
-- Mirrors AUA assertions store but scoped per user from day 1.
CREATE TABLE IF NOT EXISTS corrections (
    correction_id       TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL DEFAULT 'local',
    canonical_query     TEXT NOT NULL,
    domain              TEXT NOT NULL,
    error_type          TEXT,          -- 'complexity_wrong', 'fabricated_fact', etc.
    bad_pattern_summary TEXT,
    correction_text     TEXT NOT NULL, -- the verified correct information
    rejected_run_id     TEXT REFERENCES model_runs(run_id),  -- DPO: the bad answer
    chosen_text         TEXT,          -- DPO: the corrected answer
    confidence          REAL DEFAULT 0.9,
    decay_class         TEXT DEFAULT 'A',  -- A=permanent, B=10yr, C=3yr, D=6mo
    source              TEXT DEFAULT 'system',  -- 'system' | 'user_explicit'
    created_at          REAL NOT NULL DEFAULT (unixepoch('now')),
    last_used_at        REAL,
    use_count           INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_corr_canonical ON corrections(canonical_query);
CREATE INDEX IF NOT EXISTS idx_corr_domain ON corrections(domain);
CREATE INDEX IF NOT EXISTS idx_corr_user ON corrections(user_id);

-- ── User Context Grammar ──────────────────────────────────────────────────────
-- Personalization across chats. Learns preferences, known domains, project context.
-- Mirrors AUA v0.6 spec user_context_grammar table.
CREATE TABLE IF NOT EXISTS user_context_grammar (
    context_id          TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL DEFAULT 'local',
    domain              TEXT,          -- NULL = global preference
    key                 TEXT NOT NULL, -- e.g. 'preferred_style', 'known_stack'
    value               TEXT NOT NULL,
    source              TEXT NOT NULL DEFAULT 'inferred',
                                       -- 'user_explicit' | 'inferred' | 'correction_derived'
    confidence          REAL DEFAULT 0.8,
    last_confirmed_at   REAL,
    created_at          REAL NOT NULL DEFAULT (unixepoch('now')),
    updated_at          REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_ctx_user_domain ON user_context_grammar(user_id, domain);

-- ── Confidence State ──────────────────────────────────────────────────────────
-- EMA-updated per-domain confidence tracking.
CREATE TABLE IF NOT EXISTS confidence_state (
    state_id                TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL DEFAULT 'local',
    domain                  TEXT NOT NULL,
    confidence_value        REAL DEFAULT 0.8,
    successful_corrections  INTEGER DEFAULT 0,
    failed_corrections      INTEGER DEFAULT 0,
    updated_at              REAL NOT NULL DEFAULT (unixepoch('now')),
    UNIQUE(user_id, domain)
);

-- ── Audit Log ─────────────────────────────────────────────────────────────────
-- Privacy audit trail. Every correction stored, every context update.
-- Lets user answer: "what does this app know about me?"
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id    TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'local',
    event_type  TEXT NOT NULL,   -- 'correction_stored', 'context_updated', etc.
    payload     TEXT,            -- JSON (no raw query text)
    created_at  REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event_type);
