"""
Pytest Test Suite: Tier 2 Local Hybrid Semantic & Episodic Memory
Specification: specs/001-omni-memory-v4/spec.md (User Story 2 - Priority P2)
SLA / Constraints:
  - SQLite schema integrity, WAL mode, foreign key cascades
  - FTS5 BM25 with Vietnamese đ/Đ consonant stroke normalization
  - Defensive FTS5 query sanitization (syntax resilience against :, ., -, boolean tokens)
  - IEEE-754 float32 vector BLOB serialization & cosine similarity
  - Reciprocal Rank Fusion (RRF) smoothing with k=20 (rank-inversion elimination)
"""

import sqlite3
import struct
import math
import re
import tempfile
import os
import pytest
from typing import List, Dict, Tuple, Any, Optional


# ============================================================================
# Genuine Tier 2 Engine Reference Implementation
# ============================================================================

import unicodedata

def fold_vietnamese(text: str) -> str:
    """
    Application-level diacritic removal preserving dual-column FTS5 precision.
    Pre-converts stroked consonants (đ/Đ -> d/D) before NFD decomposition
    because Unicode NFD does not separate the horizontal bar from 'đ'.
    """
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower()


normalize_vietnamese_diacritics = fold_vietnamese


def sanitize_fts5_query(query: str) -> str:
    """Sanitize technical developer queries for safe SQLite FTS5 MATCH execution."""
    if not query:
        return '""'
    normalized = fold_vietnamese(query)
    # Replace FTS5 reserved punctuation characters with whitespace
    cleaned = re.sub(r'[\.:\-><\(\)\*"\']', ' ', normalized)
    # Strip standalone boolean and proximity operators
    tokens = [
        t for t in cleaned.split()
        if t.upper() not in {"AND", "OR", "NOT", "NEAR"}
    ]
    if not tokens:
        return '""'
    # Wrap alphanumeric terms in double quotes for safe token matching
    return " ".join(f'"{token}"' for token in tokens)


def compute_vector_norm(vector: List[float]) -> float:
    """Compute L2 Euclidean norm."""
    return math.sqrt(sum(x * x for x in vector))


def serialize_float32_blob(vector: List[float]) -> bytes:
    """Serialize Python float list into IEEE-754 float32 binary BLOB."""
    return struct.pack(f"{len(vector)}f", *vector)


def deserialize_float32_blob(blob: bytes) -> List[float]:
    """Deserialize IEEE-754 float32 binary BLOB into Python float list."""
    dim = len(blob) // 4
    return list(struct.unpack(f"{dim}f", blob))


def cosine_similarity(v1: List[float], norm1: float, v2: List[float], norm2: float) -> float:
    """Compute cosine similarity between two vectors."""
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    return dot_product / (norm1 * norm2)


def compute_rrf_score(
    lexical_rank: Optional[int],
    semantic_rank: Optional[int],
    k: int = 20,
    w_bm25: float = 0.5,
    w_dense: float = 0.5
) -> float:
    """Compute Reciprocal Rank Fusion score."""
    score = 0.0
    if lexical_rank is not None and lexical_rank > 0:
        score += w_bm25 / (k + lexical_rank)
    if semantic_rank is not None and semantic_rank > 0:
        score += w_dense / (k + semantic_rank)
    return score


DDL_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS system_capabilities (
    capability_id       TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    version             TEXT NOT NULL DEFAULT '1.0.0',
    capability_type     TEXT NOT NULL,
    source_type         TEXT NOT NULL,
    file_path           TEXT NOT NULL,
    description         TEXT NOT NULL,
    trigger_tokens      TEXT NOT NULL,
    bilingual_tags      TEXT NOT NULL,
    affinity_score      REAL NOT NULL DEFAULT 1.0,
    total_activations   INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_episodic_memory (
    memory_id           TEXT PRIMARY KEY,
    workspace_hash      TEXT NOT NULL,
    workspace_path      TEXT NOT NULL,
    memory_type         TEXT NOT NULL,
    title               TEXT NOT NULL,
    problem_signature   TEXT,
    solution_payload    TEXT NOT NULL,
    context_metadata    TEXT,
    bilingual_tags      TEXT,
    activation_count    INTEGER NOT NULL DEFAULT 1,
    confidence_score    REAL NOT NULL DEFAULT 1.0,
    decay_rate          REAL NOT NULL DEFAULT 0.05,
    last_accessed_at    TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mem_workspace_type ON workspace_episodic_memory(workspace_hash, memory_type);
CREATE INDEX IF NOT EXISTS idx_mem_last_accessed ON workspace_episodic_memory(last_accessed_at DESC);

CREATE TABLE IF NOT EXISTS dense_embeddings (
    memory_id           TEXT PRIMARY KEY,
    workspace_hash      TEXT NOT NULL,
    model_name          TEXT NOT NULL,
    dimensions          INTEGER NOT NULL,
    vector_blob         BLOB NOT NULL,
    norm                REAL NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY(memory_id) REFERENCES workspace_episodic_memory(memory_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_emb_workspace ON dense_embeddings(workspace_hash, model_name);

CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(
    memory_id UNINDEXED,
    title,
    problem_signature,
    solution_payload,
    bilingual_tags,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS trg_episodic_after_insert AFTER INSERT ON workspace_episodic_memory
BEGIN
    INSERT INTO episodic_fts(rowid, memory_id, title, problem_signature, solution_payload, bilingual_tags)
    VALUES (new.rowid, new.memory_id, new.title, coalesce(new.problem_signature, ''), new.solution_payload, coalesce(new.bilingual_tags, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_after_delete AFTER DELETE ON workspace_episodic_memory
BEGIN
    DELETE FROM episodic_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_after_update AFTER UPDATE ON workspace_episodic_memory
BEGIN
    DELETE FROM episodic_fts WHERE rowid = old.rowid;
    INSERT INTO episodic_fts(rowid, memory_id, title, problem_signature, solution_payload, bilingual_tags)
    VALUES (new.rowid, new.memory_id, new.title, coalesce(new.problem_signature, ''), new.solution_payload, coalesce(new.bilingual_tags, ''));
END;

CREATE TABLE IF NOT EXISTS activation_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    user_input          TEXT NOT NULL,
    workspace_dir       TEXT NOT NULL,
    top_skill           TEXT,
    tier_used           INTEGER NOT NULL DEFAULT 1,
    recalled_traces     TEXT,
    feedback_score      REAL DEFAULT 0.0,
    is_consolidated     INTEGER NOT NULL DEFAULT 0
);
"""


# ============================================================================
# Pytest Test Cases
# ============================================================================

@pytest.fixture
def sqlite_db():
    """Create a temporary SQLite database with WAL mode and schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(DDL_SCHEMA)
    conn.commit()

    yield conn

    conn.close()
    try:
        os.remove(path)
        wal_path = path + "-wal"
        shm_path = path + "-shm"
        if os.path.exists(wal_path):
            os.remove(wal_path)
        if os.path.exists(shm_path):
            os.remove(shm_path)
    except Exception:
        pass


def test_sqlite_wal_and_schema_ddl(sqlite_db):
    """
    Validate that SQLite initializes with WAL mode, foreign keys, and all 5 tables plus FTS5.
    """
    cur = sqlite_db.cursor()

    # Check journal mode
    cur.execute("PRAGMA journal_mode;")
    mode = cur.fetchone()[0]
    assert mode.upper() == "WAL"

    # Check foreign keys
    cur.execute("PRAGMA foreign_keys;")
    fk = cur.fetchone()[0]
    assert fk == 1

    # Check tables presence
    cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow');")
    tables = [row[0] for row in cur.fetchall()]

    assert "system_capabilities" in tables
    assert "workspace_episodic_memory" in tables
    assert "dense_embeddings" in tables
    assert "episodic_fts" in tables
    assert "activation_events" in tables


def test_fts5_vietnamese_d_stroke_normalization(sqlite_db):
    """
    Assert that Vietnamese stroke consonants (đ/Đ) normalized to d/D match 100% across accented/unaccented queries.
    """
    cur = sqlite_db.cursor()

    # 1. Insert record with Vietnamese title containing 'đ/Đ'
    raw_title = "Kiến trúc bộ nhớ đa tầng cho Omni-Kernel"
    norm_title = normalize_vietnamese_diacritics(raw_title)

    cur.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, problem_signature, solution_payload, bilingual_tags,
            last_accessed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            "mem-vi-001", "hash123", "/workspace/omni", "architecture_decision",
            norm_title, "bo nho da tang", "L1 L2 L3 cognitive hierarchy", "kien truc, da tang",
        )
    )
    sqlite_db.commit()

    # 2. Query with unaccented query "kien truc bo nho da tang"
    unaccented_query = "kien truc bo nho da tang"
    sanitized_query = sanitize_fts5_query(unaccented_query)

    cur.execute(
        "SELECT memory_id, title FROM episodic_fts WHERE episodic_fts MATCH ?",
        (sanitized_query,)
    )
    results = cur.fetchall()

    assert len(results) == 1, "Expected match for unaccented query against normalized Vietnamese text!"
    assert results[0][0] == "mem-vi-001"

    # 3. Query with accented query "kiến trúc bộ nhớ đa tầng"
    accented_query = "kiến trúc bộ nhớ đa tầng"
    sanitized_accented = sanitize_fts5_query(accented_query)

    cur.execute(
        "SELECT memory_id, title FROM episodic_fts WHERE episodic_fts MATCH ?",
        (sanitized_accented,)
    )
    results_accented = cur.fetchall()

    assert len(results_accented) == 1, "Expected match for accented query!"
    assert results_accented[0][0] == "mem-vi-001"


def test_fts5_query_sanitization_syntax_resilience(sqlite_db):
    """
    Assert that technical queries containing colons, dots, hyphens, and boolean operators execute safely.
    """
    cur = sqlite_db.cursor()

    # Insert sample technical memory
    cur.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, problem_signature, solution_payload,
            last_accessed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            "mem-tech-001", "hash123", "/workspace/test", "proven_trace",
            "Local Worker Connection Timeout", "http://127.0.0.1:8080 connection refused", "Check llama-server daemon"
        )
    )
    sqlite_db.commit()

    # Adversarial technical queries that normally cause sqlite3.OperationalError
    adversarial_queries = [
        "http://127.0.0.1:8080",
        "syntax error: near 'foo'",
        "TdrDelay >= 60",
        "NOT NULL",
        "AND",
        "OR NOT NEAR",
        "foo:bar.baz-qux()",
        "*wildcard*",
        'unmatched "quotes'
    ]

    for raw_q in adversarial_queries:
        sanitized = sanitize_fts5_query(raw_q)
        try:
            cur.execute(
                "SELECT memory_id FROM episodic_fts WHERE episodic_fts MATCH ?",
                (sanitized,)
            )
            # Fetch without error
            cur.fetchall()
        except sqlite3.OperationalError as e:
            pytest.fail(f"OperationalError thrown on sanitized query for input {raw_q!r} -> {sanitized!r}: {e}")


def test_dense_vector_blob_cosine_similarity(sqlite_db):
    """
    Assert IEEE-754 float32 vector BLOB serialization and cosine similarity evaluation.
    """
    cur = sqlite_db.cursor()

    # Insert episodic parent record
    cur.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, solution_payload, last_accessed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        ("vec-001", "ws_alpha", "/ws/alpha", "proven_trace", "Vector Test Alpha", "Payload A")
    )

    # Create 384-dim normalized vector
    dim = 384
    v1 = [1.0 / math.sqrt(dim)] * dim
    norm1 = compute_vector_norm(v1)
    blob1 = serialize_float32_blob(v1)

    cur.execute(
        """
        INSERT INTO dense_embeddings (
            memory_id, workspace_hash, model_name, dimensions, vector_blob, norm, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        ("vec-001", "ws_alpha", "intfloat/multilingual-e5-small", dim, blob1, norm1)
    )
    sqlite_db.commit()

    # Fetch and evaluate cosine similarity against identical query vector
    cur.execute("SELECT vector_blob, norm FROM dense_embeddings WHERE memory_id = ?", ("vec-001",))
    row = cur.fetchone()
    stored_blob, stored_norm = row[0], row[1]

    restored_v1 = deserialize_float32_blob(stored_blob)
    assert len(restored_v1) == dim

    sim_identical = cosine_similarity(v1, norm1, restored_v1, stored_norm)
    assert pytest.approx(sim_identical, 1e-5) == 1.0

    # Orthogonal vector test
    v_ortho = [1.0 if i == 0 else 0.0 for i in range(dim)]
    norm_ortho = compute_vector_norm(v_ortho)
    # Cosine between uniform vector and basis vector: (1 * 1/sqrt(dim)) / (1.0 * 1.0) = 1/sqrt(384) ~ 0.051
    sim_ortho = cosine_similarity(restored_v1, stored_norm, v_ortho, norm_ortho)
    expected_sim = 1.0 / math.sqrt(dim)
    assert pytest.approx(sim_ortho, 1e-5) == expected_sim


def test_reciprocal_rank_fusion_k20_monotonicity():
    """
    Validate that RRF with k=20 eliminates the rank-inversion anomaly present in k=60.
    Under k=20:
      Rank 1 single channel: 0.5 / (20 + 1) = 0.023810
      Rank 50 dual channel: 0.5 / (20 + 50) + 0.5 / (20 + 50) = 0.014286
      Result: Rank 1 single strictly beats Rank 50 dual channel (0.023810 > 0.014286).
    Under legacy k=60:
      Rank 1 single channel: 0.5 / (60 + 1) = 0.008197
      Rank 50 dual channel: 0.5 / (60 + 50) + 0.5 / (60 + 50) = 0.009091
      Result: Inverted! (Dual 50 beat Rank 1).
    """
    # Test k=20
    k20_rank1_single = compute_rrf_score(lexical_rank=1, semantic_rank=None, k=20)
    k20_rank50_dual = compute_rrf_score(lexical_rank=50, semantic_rank=50, k=20)

    assert pytest.approx(0.5 / 21.0, abs=1e-5) == k20_rank1_single
    assert pytest.approx(1.0 / 70.0, abs=1e-5) == k20_rank50_dual
    # Inversion must be ELIMINATED
    assert k20_rank1_single > k20_rank50_dual, "k=20 failed to eliminate rank inversion!"

    # Verify that legacy k=60 would have failed
    k60_rank1_single = compute_rrf_score(lexical_rank=1, semantic_rank=None, k=60)
    k60_rank50_dual = compute_rrf_score(lexical_rank=50, semantic_rank=50, k=60)
    assert k60_rank50_dual > k60_rank1_single, "k=60 was supposed to exhibit rank-inversion"


def test_foreign_key_cascade_deletion(sqlite_db):
    """
    Assert that deleting an episodic memory cascades to delete dense_embeddings and episodic_fts.
    """
    cur = sqlite_db.cursor()

    cur.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, solution_payload, last_accessed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        ("cascade-001", "hash_c", "/ws/c", "invariant", "Cascade Title", "Cascade Solution")
    )

    dim = 4
    blob = serialize_float32_blob([1.0, 0.0, 0.0, 0.0])
    cur.execute(
        """
        INSERT INTO dense_embeddings (
            memory_id, workspace_hash, model_name, dimensions, vector_blob, norm, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        ("cascade-001", "hash_c", "model_test", dim, blob, 1.0)
    )
    sqlite_db.commit()

    # Verify presence
    cur.execute("SELECT count(*) FROM dense_embeddings WHERE memory_id = 'cascade-001'")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT count(*) FROM episodic_fts WHERE memory_id = 'cascade-001'")
    assert cur.fetchone()[0] == 1

    # Delete parent
    cur.execute("DELETE FROM workspace_episodic_memory WHERE memory_id = 'cascade-001'")
    sqlite_db.commit()

    # Verify cascading removal
    cur.execute("SELECT count(*) FROM dense_embeddings WHERE memory_id = 'cascade-001'")
    assert cur.fetchone()[0] == 0, "dense_embeddings row was not cascade-deleted!"

    cur.execute("SELECT count(*) FROM episodic_fts WHERE memory_id = 'cascade-001'")
    assert cur.fetchone()[0] == 0, "episodic_fts entry was not deleted by trigger!"


def test_workspace_hash_partition_isolation(sqlite_db):
    """
    Assert that embedding queries partitioned by workspace_hash only retrieve records from that workspace.
    """
    cur = sqlite_db.cursor()

    # Insert two records in different workspaces
    for ws in ["ws_A", "ws_B"]:
        mem_id = f"mem_{ws}"
        cur.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, solution_payload, last_accessed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (mem_id, ws, f"/path/{ws}", "proven_trace", f"Title {ws}", f"Fix {ws}")
        )
        cur.execute(
            """
            INSERT INTO dense_embeddings (
                memory_id, workspace_hash, model_name, dimensions, vector_blob, norm, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (mem_id, ws, "bge-small", 4, serialize_float32_blob([1.0, 0.0, 0.0, 0.0]), 1.0)
        )
    sqlite_db.commit()

    # Query partitioned by ws_A
    cur.execute(
        "SELECT memory_id FROM dense_embeddings WHERE workspace_hash = ?",
        ("ws_A",)
    )
    rows_A = cur.fetchall()
    assert len(rows_A) == 1
    assert rows_A[0][0] == "mem_ws_A"

    # Query partitioned by ws_B
    cur.execute(
        "SELECT memory_id FROM dense_embeddings WHERE workspace_hash = ?",
        ("ws_B",)
    )
    rows_B = cur.fetchall()
    assert len(rows_B) == 1
    assert rows_B[0][0] == "mem_ws_B"


def test_offline_vector_fallback_pure_fts5(sqlite_db):
    """
    Assert that when vector search / ONNX embedding engine is unavailable/offline,
    hybrid retrieval degrades gracefully to pure FTS5 BM25 search in strictly <1.0ms
    using partitioned SQL join:
        JOIN workspace_episodic_memory e ON f.rowid = e.rowid WHERE e.workspace_hash = ?
    without throwing exceptions (User Story 2, Scenario 2.5).
    """
    import time
    cur = sqlite_db.cursor()

    ws_hash = "offline_fallback_ws"
    # Insert multiple episodic records into workspace
    cur.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, problem_signature, solution_payload, bilingual_tags,
            last_accessed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            "fallback-001", ws_hash, "/ws/offline", "proven_trace",
            "Docker Daemon Bind Port Error", "port 8080 already in use",
            "kill -9 $(lsof -t -i:8080)", "docker, port",
        )
    )
    # Insert a record in another workspace to verify partition isolation during fallback
    cur.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, problem_signature, solution_payload, bilingual_tags,
            last_accessed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            "other-001", "other_ws", "/ws/other", "proven_trace",
            "Docker Daemon Bind Port Error in Other WS", "port 8080 already in use",
            "other fix", "docker, port",
        )
    )
    sqlite_db.commit()

    # Search implementation simulating hybrid engine with vector engine offline
    def execute_hybrid_search(query_text: str, workspace_hash: str, vector_engine_online: bool = False) -> List[Dict[str, Any]]:
        # FTS5 lexical path with partitioned join on rowid
        sanitized = sanitize_fts5_query(query_text)
        cur.execute(
            """
            SELECT f.memory_id, e.title, e.solution_payload, e.workspace_hash
            FROM episodic_fts f
            JOIN workspace_episodic_memory e ON f.rowid = e.rowid
            WHERE f.episodic_fts MATCH ? AND e.workspace_hash = ?
            """,
            (sanitized, workspace_hash)
        )
        lexical_rows = cur.fetchall()

        # If vector engine is offline, degrade gracefully to pure FTS5 BM25
        if not vector_engine_online:
            results = []
            for rank, row in enumerate(lexical_rows, start=1):
                results.append({
                    "memory_id": row[0],
                    "title": row[1],
                    "solution_payload": row[2],
                    "workspace_hash": row[3],
                    "score": compute_rrf_score(lexical_rank=rank, semantic_rank=None, k=20),
                    "channel": "pure_fts5_fallback"
                })
            return results

        return []

    # Execute offline search benchmark
    t0 = time.perf_counter()
    results = execute_hybrid_search("Docker Daemon Bind Port Error", ws_hash, vector_engine_online=False)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Assertions
    assert len(results) == 1, "Expected exactly 1 isolated record for ws_hash!"
    assert results[0]["memory_id"] == "fallback-001"
    assert results[0]["workspace_hash"] == ws_hash
    assert results[0]["channel"] == "pure_fts5_fallback"
    assert results[0]["score"] > 0.0
    assert elapsed_ms < 1.0, f"Offline pure FTS5 fallback took {elapsed_ms:.4f}ms, exceeding 1.0ms SLA budget!"
