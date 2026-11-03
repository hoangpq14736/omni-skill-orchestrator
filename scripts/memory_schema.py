"""
SQLite Schema and DDL Configuration Module for Omni-Memory v4.0.
Provides database initialization, WAL pragmas, dual-column FTS5 virtual tables,
triggers, and staging tables.
"""

import sqlite3
from typing import Optional

DDL_PRAGMAS = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
"""

DDL_TABLES = """
-- ----------------------------------------------------------------------------
-- Table 1: system_capabilities
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_capabilities (
    capability_id       TEXT PRIMARY KEY,            -- e.g. 'skill:spec-driven-development'
    name                TEXT NOT NULL,               -- Canonical name
    version             TEXT NOT NULL DEFAULT '1.0.0',
    capability_type     TEXT NOT NULL,               -- 'skill', 'mcp_server', 'mcp_tool', 'rule'
    source_type         TEXT NOT NULL,               -- 'builtin', 'plugin', 'workspace', 'synthesized'
    file_path           TEXT NOT NULL,               -- Absolute path to definition
    description         TEXT NOT NULL,
    trigger_tokens      TEXT NOT NULL,               -- JSON array of keyword strings
    bilingual_tags      TEXT NOT NULL,               -- JSON array of EN/VI tags
    affinity_score      REAL NOT NULL DEFAULT 1.0,   -- Dynamic learned weight (0.1 - 5.0)
    total_activations   INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,               -- ISO-8601 UTC
    updated_at          TEXT NOT NULL                -- ISO-8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_cap_type_source ON system_capabilities(capability_type, source_type);
CREATE INDEX IF NOT EXISTS idx_cap_affinity ON system_capabilities(affinity_score DESC);

-- ----------------------------------------------------------------------------
-- Table 2: workspace_episodic_memory
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_episodic_memory (
    memory_id           TEXT PRIMARY KEY,            -- UUID v4 or SHA-256
    workspace_hash      TEXT NOT NULL,               -- MD5 hash of canonical workspace path: os.path.normcase(os.path.normpath(os.path.abspath(path)))
    workspace_path      TEXT NOT NULL,               -- Canonical workspace root path
    memory_type         TEXT NOT NULL,               -- 'invariant', 'architecture_decision', 'proven_trace', 'user_preference'
    title               TEXT NOT NULL,               -- Compact summary headline
    problem_signature   TEXT,                        -- Problem statement, regex, or error string
    solution_payload    TEXT NOT NULL,               -- Code snippet, shell command, or architectural rule
    context_metadata    TEXT,                        -- JSON: tool used, language, exit code, parameters
    bilingual_tags      TEXT,                        -- Comma-separated EN/VI tags
    content_folded      TEXT NOT NULL,               -- App-level fold_vietnamese(title + ' ' + problem_signature + ' ' + solution_payload + ' ' + tags)
    status              TEXT NOT NULL DEFAULT 'Active', -- 'Active', 'Archived', 'Superseded'
    superseded_by       TEXT,                        -- memory_id of newer replacement rule (for invariant versioning)
    activation_count    INTEGER NOT NULL DEFAULT 1,  -- Access reinforcement count
    confidence_score    REAL NOT NULL DEFAULT 1.0,   -- Initial quality metric (0.0 - 1.0)
    decay_rate          REAL NOT NULL DEFAULT 0.08,  -- Ebbinghaus lambda in day^-1 (0.0 = permanent invariant)
    last_accessed_at    TEXT NOT NULL,               -- ISO-8601 UTC timestamp
    created_at          TEXT NOT NULL                -- ISO-8601 UTC timestamp
);

CREATE INDEX IF NOT EXISTS idx_mem_workspace_type ON workspace_episodic_memory(workspace_hash, memory_type);
CREATE INDEX IF NOT EXISTS idx_mem_status ON workspace_episodic_memory(status);
CREATE INDEX IF NOT EXISTS idx_mem_last_accessed ON workspace_episodic_memory(last_accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_mem_confidence ON workspace_episodic_memory(confidence_score DESC);

-- ----------------------------------------------------------------------------
-- Table 3: dense_embeddings
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dense_embeddings (
    memory_id           TEXT PRIMARY KEY,            -- FK -> workspace_episodic_memory(memory_id)
    workspace_hash      TEXT NOT NULL,               -- Partition key for isolated workspace filtering
    model_name          TEXT NOT NULL,               -- e.g. 'intfloat/multilingual-e5-small' (INT8 quantized, 384 dim)
    dimensions          INTEGER NOT NULL DEFAULT 384,-- Dimension count: 384
    vector_blob         BLOB NOT NULL,               -- IEEE-754 float32 binary buffer (384 * 4 = 1536 bytes)
    norm                REAL NOT NULL,               -- Precomputed L2 Euclidean norm
    updated_at          TEXT NOT NULL,               -- ISO-8601 UTC timestamp
    FOREIGN KEY(memory_id) REFERENCES workspace_episodic_memory(memory_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_emb_workspace ON dense_embeddings(workspace_hash, model_name);
CREATE INDEX IF NOT EXISTS idx_emb_model ON dense_embeddings(model_name);

-- ----------------------------------------------------------------------------
-- Table 4: episodic_fts (Dual-Column FTS5 Virtual Table)
-- ----------------------------------------------------------------------------
CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(
    content_exact,
    content_folded,
    tokenize = 'unicode61 remove_diacritics 0'
);

-- Triggers for Synchronous FTS5 Maintenance with rowid Alignment
CREATE TRIGGER IF NOT EXISTS trg_episodic_after_insert AFTER INSERT ON workspace_episodic_memory
BEGIN
    INSERT INTO episodic_fts(rowid, content_exact, content_folded)
    VALUES (
        new.rowid,
        new.title || ' ' || coalesce(new.problem_signature, '') || ' ' || new.solution_payload || ' ' || coalesce(new.bilingual_tags, ''),
        new.content_folded
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_after_delete AFTER DELETE ON workspace_episodic_memory
BEGIN
    DELETE FROM episodic_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_after_update AFTER UPDATE ON workspace_episodic_memory
BEGIN
    DELETE FROM episodic_fts WHERE rowid = old.rowid;
    INSERT INTO episodic_fts(rowid, content_exact, content_folded)
    VALUES (
        new.rowid,
        new.title || ' ' || coalesce(new.problem_signature, '') || ' ' || new.solution_payload || ' ' || coalesce(new.bilingual_tags, ''),
        new.content_folded
    );
END;

-- ----------------------------------------------------------------------------
-- Table 5: l1_staging_log (Lightweight Ephemeral Staging Buffer for L1 Reflex)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS l1_staging_log (
    staging_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,               -- ISO-8601 UTC
    user_input          TEXT NOT NULL,
    workspace_hash      TEXT NOT NULL,
    top_skill           TEXT,
    tier_used           INTEGER NOT NULL DEFAULT 1,
    recalled_traces     TEXT,                        -- JSON array of recalled memory IDs
    is_drained          INTEGER NOT NULL DEFAULT 0   -- 0 = pending, 1 = processed by Memory Daemon Single-Writer
);

-- ----------------------------------------------------------------------------
-- Table 6: activation_events (Tier 3 Consolidation Staging Buffer)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activation_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    user_input          TEXT NOT NULL,
    workspace_dir       TEXT NOT NULL,
    top_skill           TEXT,
    tier_used           INTEGER NOT NULL DEFAULT 1,
    recalled_traces     TEXT,                        -- JSON array of recalled memory IDs
    feedback_score      REAL DEFAULT 0.0,            -- +1.0 (success), 0.0 (neutral), -1.0 (failure)
    is_consolidated     INTEGER NOT NULL DEFAULT 0   -- 0 = pending, 1 = processed
);

CREATE INDEX IF NOT EXISTS idx_event_pending ON activation_events(is_consolidated, timestamp);
"""


def init_database(db_path: str = "omni_memory.db") -> sqlite3.Connection:
    """
    Initialize SQLite database with production pragmas, tables, triggers, and indexes.
    Returns the active database connection.
    """
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row

    # Verify auto_vacuum mode (2 == INCREMENTAL).
    # CRITICAL: VACUUM cannot be run inside a transaction; isolation_level must be None
    try:
        mode = conn.execute("PRAGMA auto_vacuum;").fetchone()[0]
        if mode != 2:
            old_iso = conn.isolation_level
            conn.isolation_level = None
            conn.execute("PRAGMA auto_vacuum = INCREMENTAL;")
            conn.execute("VACUUM;")
            conn.isolation_level = old_iso
    except Exception:
        pass
    
    # Apply pragmas
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA mmap_size = 268435456;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Execute DDL
    conn.executescript(DDL_TABLES)
    conn.commit()
    return conn
