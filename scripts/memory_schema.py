"""
SQLite Schema and DDL Configuration Module for Omni-Memory v4.1.
Provides database initialization, WAL pragmas, dual-column FTS5 virtual tables,
triggers, and staging tables.
"""

import sqlite3
import uuid
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
WHEN (
    new.title IS NOT old.title OR
    new.problem_signature IS NOT old.problem_signature OR
    new.solution_payload IS NOT old.solution_payload OR
    new.bilingual_tags IS NOT old.bilingual_tags OR
    new.content_folded IS NOT old.content_folded
)
BEGIN
    DELETE FROM episodic_fts WHERE rowid = old.rowid;
    INSERT INTO episodic_fts(rowid, content_exact, content_folded)
    VALUES (
        new.rowid,
        new.title || ' ' || coalesce(new.problem_signature, '') || ' ' || new.solution_payload || ' ' || coalesce(new.bilingual_tags, ''),
        new.content_folded
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_prevent_ws_replace
BEFORE INSERT ON workspace_episodic_memory
FOR EACH ROW
WHEN EXISTS (
    SELECT 1 FROM workspace_episodic_memory
    WHERE memory_id = new.memory_id AND workspace_hash IS NOT new.workspace_hash
)
BEGIN
    SELECT RAISE(ABORT, 'workspace_hash is immutable and cannot be replaced with a different tenant hash');
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_prevent_cross_tenant_supersede
BEFORE UPDATE OF superseded_by ON workspace_episodic_memory
FOR EACH ROW
WHEN new.superseded_by IS NOT NULL AND EXISTS (
    SELECT 1 FROM workspace_episodic_memory target
    WHERE target.memory_id = new.superseded_by AND target.workspace_hash IS NOT new.workspace_hash
)
BEGIN
    SELECT RAISE(ABORT, 'superseded_by cannot reference a record from a different workspace_hash');
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_prevent_cross_tenant_supersede_insert
BEFORE INSERT ON workspace_episodic_memory
FOR EACH ROW
WHEN new.superseded_by IS NOT NULL AND EXISTS (
    SELECT 1 FROM workspace_episodic_memory target
    WHERE target.memory_id = new.superseded_by AND target.workspace_hash IS NOT new.workspace_hash
)
BEGIN
    SELECT RAISE(ABORT, 'superseded_by cannot reference a record from a different workspace_hash');
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_prevent_ws_update BEFORE UPDATE OF workspace_hash ON workspace_episodic_memory
WHEN new.workspace_hash IS NOT old.workspace_hash
BEGIN
    SELECT RAISE(ABORT, 'workspace_hash is immutable and cannot be transferred across tenants');
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
    is_drained          INTEGER NOT NULL DEFAULT 0,  -- 0 = pending, 1 = processed, 2 = quarantined
    last_error          TEXT                         -- Diagnostic context for quarantined rows
);

CREATE INDEX IF NOT EXISTS idx_staging_status_ws ON l1_staging_log (is_drained, workspace_hash, staging_id);

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
    is_consolidated     INTEGER NOT NULL DEFAULT 0,  -- 0 = pending, 1 = processed, 2 = quarantined
    last_error          TEXT                         -- Diagnostic context for quarantined events (VULN-006)
);

CREATE INDEX IF NOT EXISTS idx_event_pending ON activation_events(is_consolidated, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_status_ws ON activation_events (is_consolidated, workspace_dir, event_id);

-- ----------------------------------------------------------------------------
-- Table 7: consolidation_outbox (Durable Outbox Queue for Proven Traces)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consolidation_outbox (
    outbox_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id           TEXT NOT NULL,
    workspace_hash      TEXT NOT NULL,
    signature           TEXT NOT NULL,
    solution            TEXT NOT NULL,
    tags                TEXT,
    context             TEXT,
    status              TEXT NOT NULL DEFAULT 'Pending', -- 'Pending', 'InFlight', 'Flushed', 'Failed'
    generation          INTEGER NOT NULL DEFAULT 1,      -- Incremented on re-promotion to preserve reinforcement (VULN-004)
    retry_count         INTEGER NOT NULL DEFAULT 0,
    last_error          TEXT,
    created_at          TEXT NOT NULL,
    claimed_at          TEXT,                        -- Timestamp when claimed as InFlight (VULN-001)
    owner_token         TEXT,                        -- Unique claim lease token for atomic CAS commit (Hazard 43)
    flushed_at          TEXT,
    UNIQUE(memory_id, workspace_hash)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_outbox_mem_ws ON consolidation_outbox (memory_id, workspace_hash);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON consolidation_outbox(status);
CREATE INDEX IF NOT EXISTS idx_outbox_status_ws ON consolidation_outbox (status, workspace_hash, outbox_id);

-- ----------------------------------------------------------------------------
-- Table 8: workspace_registry (Tenancy Isolation & Sub-Workspace Registry)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_registry (
    workspace_hash      TEXT PRIMARY KEY,            -- Hex hash (32 or 64 char)
    workspace_path      TEXT NOT NULL,               -- Canonical filesystem root path
    registered_at       TEXT NOT NULL                -- ISO-8601 UTC timestamp
);
"""


def init_database(db_path: str = "omni_memory.db", isolation_level: Optional[str] = None) -> sqlite3.Connection:
    """
    Initialize SQLite database with production pragmas, tables, triggers, and indexes.
    Defaults to isolation_level=None (autocommit) to safely support manual BEGIN IMMEDIATE (VULN-006).
    Returns the active database connection.
    """
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=isolation_level)
    conn.row_factory = sqlite3.Row

    # Verify auto_vacuum mode (2 == INCREMENTAL).
    # CRITICAL: VACUUM cannot be run inside a transaction; isolation_level must be None
    try:
        mode = conn.execute("PRAGMA auto_vacuum;").fetchone()[0]
        if mode != 2:
            old_iso = conn.isolation_level
            try:
                conn.isolation_level = None
                conn.execute("PRAGMA auto_vacuum = INCREMENTAL;")
                conn.execute("VACUUM;")
            finally:
                conn.isolation_level = old_iso
    except Exception as e:
        import sys
        sys.stderr.write(f"[!] Warning: auto_vacuum configuration skipped ({type(e).__name__}: {e})\n")
    
    # Apply pragmas
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA mmap_size = 268435456;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Migration: Add columns to existing tables if missing with fail-loud OperationalError handling (VULN-004)
    cols_ob = [row[1] for row in conn.execute("PRAGMA table_info(consolidation_outbox);").fetchall()]
    if cols_ob:
        if "claimed_at" not in cols_ob:
            try:
                conn.execute("ALTER TABLE consolidation_outbox ADD COLUMN claimed_at TEXT;")
            except sqlite3.OperationalError as oe:
                if "duplicate column name" not in str(oe).lower():
                    raise RuntimeError(f"Failed to migrate consolidation_outbox.claimed_at: {oe}") from oe
        if "owner_token" not in cols_ob:
            try:
                conn.execute("ALTER TABLE consolidation_outbox ADD COLUMN owner_token TEXT;")
            except sqlite3.OperationalError as oe:
                if "duplicate column name" not in str(oe).lower():
                    raise RuntimeError(f"Failed to migrate consolidation_outbox.owner_token: {oe}") from oe
        if "generation" not in cols_ob:
            try:
                conn.execute("ALTER TABLE consolidation_outbox ADD COLUMN generation INTEGER NOT NULL DEFAULT 1;")
            except sqlite3.OperationalError as oe:
                if "duplicate column name" not in str(oe).lower():
                    raise RuntimeError(f"Failed to migrate consolidation_outbox.generation: {oe}") from oe

        # VULN-002: Ensure UNIQUE constraint on (memory_id, workspace_hash) for legacy DBs via unique index
        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_outbox_mem_ws ON consolidation_outbox (memory_id, workspace_hash);")
        except Exception as uidx_err:
            raise RuntimeError(f"Failed to ensure unique index idx_outbox_mem_ws: {uidx_err}") from uidx_err

    cols_l1 = [row[1] for row in conn.execute("PRAGMA table_info(l1_staging_log);").fetchall()]
    if cols_l1 and "last_error" not in cols_l1:
        try:
            conn.execute("ALTER TABLE l1_staging_log ADD COLUMN last_error TEXT;")
        except sqlite3.OperationalError as oe:
            if "duplicate column name" not in str(oe).lower():
                raise RuntimeError(f"Failed to migrate l1_staging_log.last_error: {oe}") from oe

    # Migration for activation_events.last_error (VULN-006)
    cols_ae = [row[1] for row in conn.execute("PRAGMA table_info(activation_events);").fetchall()]
    if cols_ae and "last_error" not in cols_ae:
        try:
            conn.execute("ALTER TABLE activation_events ADD COLUMN last_error TEXT;")
        except sqlite3.OperationalError as oe:
            if "duplicate column name" not in str(oe).lower():
                raise RuntimeError(f"Failed to migrate activation_events.last_error: {oe}") from oe

    # VULN-003: Drop triggers before running legacy MD5->SHA-256 migration to avoid RAISE(ABORT)
    conn.execute("DROP TRIGGER IF EXISTS trg_episodic_prevent_ws_update;")
    conn.execute("DROP TRIGGER IF EXISTS trg_episodic_prevent_ws_replace;")
    conn.execute("DROP TRIGGER IF EXISTS trg_episodic_after_update;")
    conn.execute("DROP TRIGGER IF EXISTS trg_episodic_prevent_cross_tenant_supersede;")
    conn.execute("DROP TRIGGER IF EXISTS trg_episodic_prevent_cross_tenant_supersede_insert;")

    # VULN-002 & VULN-001: Dual-key migration for legacy MD5 (32-hex) to canonical SHA-256 (64-hex)
    tables_exist = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    sp_mig = f"sp_mig_{uuid.uuid4().hex[:8]}"
    conn.execute(f"SAVEPOINT {sp_mig};")
    try:
        from memory_utils import canonical_workspace_hash
        hash_to_path = {}
        if "workspace_registry" in tables_exist:
            for r_h, r_p in conn.execute("SELECT workspace_hash, workspace_path FROM workspace_registry;").fetchall():
                hash_to_path[r_h] = r_p

        legacy_hashes = set()
        if "workspace_episodic_memory" in tables_exist:
            for row in conn.execute("SELECT DISTINCT workspace_hash FROM workspace_episodic_memory WHERE length(workspace_hash) = 32;").fetchall():
                legacy_hashes.add(row[0])
        if "consolidation_outbox" in tables_exist:
            for row in conn.execute("SELECT DISTINCT workspace_hash FROM consolidation_outbox WHERE length(workspace_hash) = 32;").fetchall():
                legacy_hashes.add(row[0])

        for old_hash in legacy_hashes:
            known_path = hash_to_path.get(old_hash)
            if known_path:
                new_hash = canonical_workspace_hash(known_path)
            else:
                new_hash = canonical_workspace_hash(f"legacy_partition:{old_hash}")
            
            if new_hash and len(new_hash) == 64 and new_hash != old_hash:
                if "workspace_episodic_memory" in tables_exist:
                    conn.execute("UPDATE workspace_episodic_memory SET workspace_hash = ? WHERE workspace_hash = ?;", (new_hash, old_hash))
                if "dense_embeddings" in tables_exist:
                    conn.execute("UPDATE dense_embeddings SET workspace_hash = ? WHERE workspace_hash = ?;", (new_hash, old_hash))
                if "activation_events" in tables_exist:
                    conn.execute("UPDATE activation_events SET workspace_dir = ? WHERE workspace_dir = ?;", (new_hash, old_hash))
                if "consolidation_outbox" in tables_exist:
                    conn.execute("UPDATE consolidation_outbox SET workspace_hash = ? WHERE workspace_hash = ?;", (new_hash, old_hash))
                if "workspace_registry" in tables_exist and known_path:
                    conn.execute("INSERT OR IGNORE INTO workspace_registry (workspace_hash, workspace_path, registered_at) VALUES (?, ?, datetime('now'));", (new_hash, known_path))
        conn.execute(f"RELEASE SAVEPOINT {sp_mig};")
    except Exception as mig_err:
        try:
            conn.execute(f"ROLLBACK TO SAVEPOINT {sp_mig};")
            conn.execute(f"RELEASE SAVEPOINT {sp_mig};")
        except Exception:
            pass
        raise RuntimeError(f"Database migration from MD5 to SHA-256 failed: {mig_err}") from mig_err

    # Atomic Migration: Refresh triggers and apply DDL in a single atomic transaction with explicit rollback (VULN-008)
    atomic_ddl = f"""
    BEGIN IMMEDIATE;
    DROP TRIGGER IF EXISTS trg_episodic_after_update;
    DROP TRIGGER IF EXISTS trg_episodic_prevent_ws_replace;
    DROP TRIGGER IF EXISTS trg_episodic_prevent_cross_tenant_supersede;
    DROP TRIGGER IF EXISTS trg_episodic_prevent_cross_tenant_supersede_insert;
    DROP TRIGGER IF EXISTS trg_episodic_prevent_ws_update;
    {DDL_TABLES}
    COMMIT;
    """
    try:
        conn.executescript(atomic_ddl)
    except Exception as ddl_err:
        try:
            conn.execute("ROLLBACK;")
        except Exception:
            pass
        raise RuntimeError(f"Atomic DDL migration failed: {type(ddl_err).__name__}: {ddl_err}") from ddl_err

    # VULN-002: Verify consolidation_outbox has unique constraint or unique index for ON CONFLICT
    has_outbox = bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='consolidation_outbox';").fetchone())
    if has_outbox:
        idx_list = conn.execute("PRAGMA index_list('consolidation_outbox');").fetchall()
        has_unique = any(row[2] == 1 for row in idx_list)
        if not has_unique:
            raise RuntimeError("CRITICAL MIGRATION ERROR: consolidation_outbox lacks a unique constraint or unique index!")

    # Post-migration schema integrity verification (VULN-004: Explicit RuntimeError checks to survive python -O)
    verified_ob = [r[1] for r in conn.execute("PRAGMA table_info(consolidation_outbox);").fetchall()]
    if "claimed_at" not in verified_ob or "owner_token" not in verified_ob or "generation" not in verified_ob:
        raise RuntimeError(f"consolidation_outbox missing required migration columns (expected claimed_at, owner_token, generation; found {verified_ob})")
    verified_l1 = [r[1] for r in conn.execute("PRAGMA table_info(l1_staging_log);").fetchall()]
    if "last_error" not in verified_l1:
        raise RuntimeError(f"l1_staging_log missing last_error column (expected last_error; found {verified_l1})")
    verified_ae = [r[1] for r in conn.execute("PRAGMA table_info(activation_events);").fetchall()]
    if "last_error" not in verified_ae:
        raise RuntimeError(f"activation_events missing last_error column (expected last_error; found {verified_ae})")

    return conn
