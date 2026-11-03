"""
Tier 2 SQLite Engine and Hybrid Semantic/Episodic Retrieval for Omni-Memory v4.1.
Provides thread-safe Single-Writer queue, dual-column FTS5 search with runtime guardrails,
vector similarity evaluation, and Reciprocal Rank Fusion (k=20).
100% Python Standard Library.
"""

import math
import os
import queue
import sqlite3
import struct
import threading
from typing import Dict, List, Optional, Tuple, Any

from memory_utils import fold_vietnamese, sanitize_fts5_query, canonical_workspace_hash


# ============================================================================
# Vector Serialization & Cosine Similarity (IEEE-754 float32)
# ============================================================================

def serialize_float32_blob(vector: List[float]) -> bytes:
    """Pack a list of floats into IEEE-754 float32 binary representation."""
    if len(vector) == 0:
        return b""
    return struct.pack(f"{len(vector)}f", *vector)


def deserialize_float32_blob(blob: bytes) -> List[float]:
    """Unpack IEEE-754 float32 binary data back into a list of floats."""
    if not blob:
        return []
    if len(blob) % 4 != 0:
        raise ValueError("Blob length must be a multiple of 4 bytes for float32 data.")
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def compute_vector_norm(vector: List[float]) -> float:
    """Return the Euclidean (L2) norm of a vector."""
    return math.sqrt(sum(x * x for x in vector))


def cosine_similarity(v1: List[float], norm1: float, v2: List[float], norm2: float) -> float:
    """Cosine similarity between two vectors given their pre-computed norms."""
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    length = min(len(v1), len(v2))
    dot = sum(v1[i] * v2[i] for i in range(length))
    return dot / (norm1 * norm2)


# ============================================================================
# Reciprocal Rank Fusion (RRF k=20)
# ============================================================================

def reciprocal_rank_fusion(
    lexical_ranked_ids: List[str],
    dense_ranked_ids: List[str],
    k: int = 20,
    w_lex: float = 0.5,
    w_dense: float = 0.5,
) -> List[Tuple[str, float]]:
    """
    Combine lexical and dense rankings using Reciprocal Rank Fusion.
    Standardized at k=20 to completely resolve the rank-inversion defect.
    """
    lex_ranks = {doc_id: rank for rank, doc_id in enumerate(lexical_ranked_ids, start=1)}
    dense_ranks = {doc_id: rank for rank, doc_id in enumerate(dense_ranked_ids, start=1)}

    all_ids = set(lex_ranks) | set(dense_ranks)
    fused: List[Tuple[str, float]] = []

    for doc_id in all_ids:
        score = 0.0
        if doc_id in lex_ranks:
            score += w_lex / (k + lex_ranks[doc_id])
        if doc_id in dense_ranks:
            score += w_dense / (k + dense_ranks[doc_id])
        fused.append((doc_id, score))

    fused.sort(key=lambda x: -x[1])
    return fused


# ============================================================================
# Single-Writer Thread Queue (SQLite Concurrency Invariant)
# ============================================================================

class MemorySingleWriter:
    """
    Thread-safe Single-Writer queue pattern for SQLite database.
    Owns exclusive write access using BEGIN IMMEDIATE transactions and PRAGMA busy_timeout=5000.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._worker_thread.start()

    def _run_worker(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA wal_autocheckpoint = 1000;")

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                task = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if task is None:
                self._queue.task_done()
                break

            sql, params, callback = task
            try:
                conn.execute("BEGIN IMMEDIATE;")
                if isinstance(sql, list):
                    for stmt, p in sql:
                        conn.execute(stmt, p)
                else:
                    conn.execute(sql, params)
                conn.commit()
                if callback:
                    callback(True, None)
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                if callback:
                    callback(False, e)
            finally:
                self._queue.task_done()

        conn.close()

    def enqueue_write(self, sql: Any, params: tuple = (), callback: Optional[Any] = None):
        """Enqueue a write task (single statement or list of statements)."""
        self._queue.put((sql, params, callback))

    def flush(self):
        """Wait until all queued writes are completed."""
        self._queue.join()

    def close(self):
        """Stop worker thread and wait for completion."""
        self._stop_event.set()
        self._queue.put(None)
        self._worker_thread.join(timeout=2.0)


# ============================================================================
# Dual-Column FTS5 Search & Hybrid Retrieval
# ============================================================================

def search_fts5(
    conn: sqlite3.Connection,
    query: str,
    workspace_hash: str,
    limit: int = 30
) -> List[Tuple[str, float]]:
    """
    Dual-column FTS5 BM25 search with MANDATORY RUNTIME GUARDRAIL.
    - :raw_q: uses fold=False to keep Vietnamese diacritics for content_exact (10.0 weight).
    - :folded_q: uses fold=True to match folded text in content_folded (1.0 weight).
    - Partitions by workspace_hash and filters out 'Superseded' records.
    - Orders by rank_score ASC (SQLite FTS5 bm25 returns negative values).
    """
    raw_q = sanitize_fts5_query(query, fold=False)
    folded_q = sanitize_fts5_query(query, fold=True)

    sql = """
    SELECT e.memory_id, bm25(episodic_fts, 10.0, 1.0) AS rank_score
    FROM episodic_fts
    JOIN workspace_episodic_memory e ON episodic_fts.rowid = e.rowid
    WHERE episodic_fts MATCH 'content_exact : (' || :raw_q || ') OR content_folded : (' || :folded_q || ')'
      AND e.workspace_hash = :ws_hash
      AND e.status != 'Superseded'
    ORDER BY rank_score ASC
    LIMIT :limit;
    """

    cursor = conn.cursor()
    cursor.execute(sql, {
        "raw_q": raw_q,
        "folded_q": folded_q,
        "ws_hash": workspace_hash,
        "limit": limit
    })
    return cursor.fetchall()


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    workspace_hash: str,
    query_vector: Optional[List[float]] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Hybrid semantic & episodic retrieval with automatic fallback to pure FTS5 BM25.
    1. Executes dual-column FTS5 search for candidate pool.
    2. If query_vector is None or empty: immediately returns pure FTS5 results.
    3. If query_vector is present: fetches candidate dense vector blobs, evaluates
       in-memory cosine similarity, fuses rankings via RRF (k=20).
    4. Hydrates and returns full dictionary records from workspace_episodic_memory.
    """
    lex_results = search_fts5(conn, query, workspace_hash, limit=50)
    if not lex_results:
        return []

    lex_ranked_ids = [row[0] for row in lex_results]

    # Offline / Fallback Path: pure FTS5 BM25
    if query_vector is None or len(query_vector) == 0:
        target_ids = lex_ranked_ids[:top_k]
    else:
        # Evaluate Dense Cosine Similarity against candidates in workspace
        cursor = conn.cursor()
        query_norm = compute_vector_norm(query_vector)

        cursor.execute(
            """
            SELECT memory_id, vector_blob, norm
            FROM dense_embeddings
            WHERE workspace_hash = ?
            """,
            (workspace_hash,)
        )
        rows = cursor.fetchall()

        dense_scored: List[Tuple[str, float]] = []
        for mem_id, blob, stored_norm in rows:
            try:
                candidate_vec = deserialize_float32_blob(blob)
                sim = cosine_similarity(query_vector, query_norm, candidate_vec, stored_norm)
                dense_scored.append((mem_id, sim))
            except Exception:
                continue

        dense_scored.sort(key=lambda x: -x[1])
        dense_ranked_ids = [m_id for m_id, _ in dense_scored]

        # Reciprocal Rank Fusion (k=20)
        fused = reciprocal_rank_fusion(lex_ranked_ids, dense_ranked_ids, k=20, w_lex=0.5, w_dense=0.5)
        target_ids = [doc_id for doc_id, _ in fused[:top_k]]

    if not target_ids:
        return []

    # Hydrate records from workspace_episodic_memory
    placeholders = ",".join("?" for _ in target_ids)
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT memory_id, workspace_hash, workspace_path, memory_type,
               title, problem_signature, solution_payload, context_metadata,
               bilingual_tags, status, activation_count, confidence_score
        FROM workspace_episodic_memory
        WHERE memory_id IN ({placeholders})
        """,
        target_ids
    )

    id_to_record = {row[0]: dict(zip(
        ["memory_id", "workspace_hash", "workspace_path", "memory_type",
         "title", "problem_signature", "solution_payload", "context_metadata",
         "bilingual_tags", "status", "activation_count", "confidence_score"],
        row
    )) for row in cursor.fetchall()}

    # Preserve ranking order
    hydrated = [id_to_record[m_id] for m_id in target_ids if m_id in id_to_record]
    return hydrated


# ============================================================================
# Invariant Versioning & Rollback API (Argon Chốt chặn 4)
# ============================================================================

def revert_invariant(conn: sqlite3.Connection, superseded_id: str) -> bool:
    """
    Safely revert a superseded invariant back to 'Active', maintaining ACID transaction integrity.
    Follows the 3 atomic steps mandated by Argon:
    1. Trace the chain of replacement: From superseded_id (V1), follow superseded_by to find
       the currently 'Active' record (V2 or last in chain).
    2. Demote the incorrect active record (V2) to 'Superseded' and point superseded_by back to V1.
    3. Re-promote V1 back to 'Active', clear superseded_by to NULL, and update last_accessed_at.
    """
    cur = conn.cursor()
    try:
        conn.execute("BEGIN IMMEDIATE;")

        # Step 1: Verify superseded_id exists
        cur.execute("SELECT memory_id, status, superseded_by FROM workspace_episodic_memory WHERE memory_id = ?", (superseded_id,))
        v1_row = cur.fetchone()
        if not v1_row:
            conn.rollback()
            return False

        # Trace forward to find the current 'Active' record in the replacement chain
        curr_id = v1_row[2]  # superseded_by
        active_target_id = None
        visited = {superseded_id}

        while curr_id and curr_id not in visited:
            visited.add(curr_id)
            cur.execute("SELECT memory_id, status, superseded_by FROM workspace_episodic_memory WHERE memory_id = ?", (curr_id,))
            row = cur.fetchone()
            if not row:
                break
            if row[1] == "Active":
                active_target_id = row[0]
                break
            curr_id = row[2]

        # Step 2: Demote active record (if found)
        if active_target_id:
            cur.execute(
                """
                UPDATE workspace_episodic_memory
                SET status = 'Superseded', superseded_by = ?
                WHERE memory_id = ?
                """,
                (superseded_id, active_target_id)
            )

        # Step 3: Re-promote original record V1
        cur.execute(
            """
            UPDATE workspace_episodic_memory
            SET status = 'Active', superseded_by = NULL, last_accessed_at = datetime('now')
            WHERE memory_id = ?
            """,
            (superseded_id,)
        )

        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
