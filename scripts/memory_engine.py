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
import sys
import threading
import time
import uuid
from typing import Dict, List, Optional, Tuple, Any

_local = threading.local()

from memory_utils import fold_vietnamese, sanitize_fts5_query, canonical_workspace_hash, redact_secrets, is_valid_hex_hash, persist_diag


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


def cosine_similarity(v1: List[float], norm1: float, v2: List[float], norm2: float, strict: bool = False) -> float:
    """
    Cosine similarity between two vectors given their pre-computed norms.
    Strict mode (strict=True) raises ValueError on dimension mismatch or invalid norms (VULN-006).
    """
    if not math.isfinite(norm1) or not math.isfinite(norm2):
        if strict:
            raise ValueError(f"Non-finite vector norm detected: norm1={norm1}, norm2={norm2}")
        return 0.0
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    if len(v1) != len(v2):
        if strict:
            raise ValueError(f"Vector dimension mismatch: len(v1)={len(v1)} != len(v2)={len(v2)}")
        return 0.0
    dot = sum(v1[i] * v2[i] for i in range(len(v1)))
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
    Employs condition variable completion signaling with zero joiner thread leaks.
    """

    def __init__(self, db_path: str, max_queue_size: int = 10000):
        self.db_path = db_path
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._seq_lock = threading.Lock()
        self._cond = threading.Condition()
        self._sequence = 0
        self._committed_sequence = 0
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._fatal_error: Optional[Exception] = None
        self._failed_sequences: Dict[int, Exception] = {}
        self._evicted_failures_count = 0
        self._closed = False
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._worker_thread.start()
        # Wait up to 5s for worker startup
        if not self._ready_event.wait(timeout=5.0):
            self._stop_event.set()
            self._worker_thread.join(timeout=1.0)
            raise TimeoutError("MemorySingleWriter worker thread failed to initialize within 5.0s")
        if self._fatal_error:
            self._stop_event.set()
            self._worker_thread.join(timeout=1.0)
            raise RuntimeError(f"MemorySingleWriter failed to start: {self._fatal_error}")

    def _run_worker(self):
        conn = None
        _local.is_worker = True
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA wal_autocheckpoint = 1000;")
            self._ready_event.set()

            while not self._stop_event.is_set() or not self._queue.empty():
                try:
                    task = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if task is None:
                    self._queue.task_done()
                    if self._queue.empty():
                        break
                    continue

                seq, sql, params, callback = task
                success = False
                err = None
                try:
                    conn.execute("BEGIN IMMEDIATE;")
                    if isinstance(sql, list):
                        for stmt, p in sql:
                            conn.execute(stmt, p)
                    else:
                        conn.execute(sql, params)
                    conn.commit()
                    success = True
                except Exception as e:
                    err = e
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                finally:
                    cb_failed = False
                    if callback:
                        try:
                            callback(success, err)
                        except Exception as cb_err:
                            cb_failed = True
                            sys.stderr.write(f"[!] Warning: MemorySingleWriter callback raised: {cb_err}\n")
                    elif not success:
                        sys.stderr.write(f"[!] LỖI MemorySingleWriter write failure (no callback): {type(err).__name__}: {err}\n")
                    
                    with self._cond:
                        if not success:
                            self._failed_sequences[seq] = err or RuntimeError(f"Task {seq} failed")
                            # Bound failures to last 256 items to prevent unbounded memory growth (Hazard 46)
                            if len(self._failed_sequences) > 256:
                                oldest_key = min(self._failed_sequences.keys())
                                del self._failed_sequences[oldest_key]
                                self._evicted_failures_count += 1
                        self._committed_sequence = max(self._committed_sequence, seq)
                        self._cond.notify_all()
                    self._queue.task_done()
        except Exception as startup_err:
            self._fatal_error = startup_err
            with self._cond:
                self._cond.notify_all()
            self._ready_event.set()
        finally:
            with self._seq_lock:
                if not self._closed and not self._fatal_error:
                    self._fatal_error = RuntimeError("MemorySingleWriter worker thread terminated unexpectedly.")
            with self._cond:
                self._cond.notify_all()
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def enqueue_write(self, sql: Any, params: tuple = (), callback: Optional[Any] = None, timeout: float = 5.0):
        """Enqueue a write task with monotonic sequence assignment."""
        if getattr(_local, "is_worker", False):
            raise RuntimeError("Cannot call enqueue_write() from within MemorySingleWriter worker thread.")
        deadline = time.monotonic() + timeout
        while True:
            with self._seq_lock:
                if self._closed:
                    raise RuntimeError("MemorySingleWriter is closed.")
                if self._fatal_error:
                    raise RuntimeError(f"MemorySingleWriter worker died: {self._fatal_error}")
                if not self._worker_thread.is_alive():
                    raise RuntimeError("MemorySingleWriter worker thread is no longer running.")
                try:
                    next_seq = self._sequence + 1
                    self._queue.put_nowait((next_seq, sql, params, callback))
                    self._sequence = next_seq
                    return next_seq
                except queue.Full:
                    pass
            if time.monotonic() >= deadline:
                raise TimeoutError("MemorySingleWriter queue full; write backpressure limit exceeded.")
            time.sleep(0.005)

    def flush(self, timeout: float = 10.0):
        """Wait until all queued writes up to target sequence are committed within bounded timeout."""
        if getattr(_local, "is_worker", False):
            raise RuntimeError("Cannot call flush() from within MemorySingleWriter worker thread.")
        with self._seq_lock:
            target_seq = self._sequence

        deadline = time.monotonic() + timeout
        with self._cond:
            while self._committed_sequence < target_seq:
                if self._fatal_error:
                    raise RuntimeError(f"MemorySingleWriter worker encountered fatal error: {self._fatal_error}")
                if not self._worker_thread.is_alive():
                    raise RuntimeError("MemorySingleWriter worker thread died during flush.")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"MemorySingleWriter flush exceeded timeout of {timeout:.1f}s (committed {self._committed_sequence}/{target_seq}).")
                self._cond.wait(timeout=min(0.05, remaining))

            if self._evicted_failures_count > 0:
                evicted = self._evicted_failures_count
                self._evicted_failures_count = 0
                raise RuntimeError(f"MemorySingleWriter encountered {evicted} evicted write failure(s) prior to flush.")

            matching_failures = [e for s, e in self._failed_sequences.items() if s <= target_seq]
            if matching_failures:
                # Prune consumed failures for callers
                self._failed_sequences = {s: e for s, e in self._failed_sequences.items() if s > target_seq}
                raise RuntimeError(f"MemorySingleWriter encountered {len(matching_failures)} write failure(s): {matching_failures[0]}")

    def close(self, timeout: float = 5.0) -> int:
        """
        Stop worker thread cleanly with deterministic drain (VULN-005).
        Returns the number of dropped/unprocessed tasks if any, rather than raising mid-teardown.
        """
        if getattr(_local, "is_worker", False):
            raise RuntimeError("Cannot call close() from within MemorySingleWriter worker thread.")
        with self._seq_lock:
            if self._closed:
                return 0
            self._closed = True

        deadline = time.monotonic() + timeout
        # Deterministic drain: attempt to flush queued writes before stopping
        try:
            drain_timeout = max(0.1, timeout * 0.7)
            self.flush(timeout=drain_timeout)
        except Exception as drain_err:
            sys.stderr.write(f"[!] Warning: MemorySingleWriter flush during close() encountered: {drain_err}\n")

        self._stop_event.set()
        try:
            put_timeout = max(0.1, min(1.0, deadline - time.monotonic()))
            self._queue.put(None, timeout=put_timeout)
        except queue.Full:
            pass

        rem_timeout = max(0.1, deadline - time.monotonic())
        self._worker_thread.join(timeout=rem_timeout)
        timed_out = self._worker_thread.is_alive()
        if timed_out:
            with self._seq_lock:
                self._fatal_error = TimeoutError(f"MemorySingleWriter worker thread failed to terminate within {timeout:.1f}s.")
            sys.stderr.write(f"[!] Warning: MemorySingleWriter worker thread failed to terminate within {timeout:.1f}s.\n")

        raw_unfinished = self._queue.unfinished_tasks
        dropped = max(0, raw_unfinished - (1 if self._stop_event.is_set() else 0))
        if dropped > 0 or timed_out:
            sys.stderr.write(f"[!] Warning: MemorySingleWriter closed with {dropped} uncompleted task(s) (timed_out={timed_out}).\n")
        return dropped


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

    clauses = []
    if raw_q and raw_q != '""':
        clauses.append(f"content_exact : ({raw_q})")
    if folded_q and folded_q != '""':
        clauses.append(f"content_folded : ({folded_q})")

    # VULN Guard: If no valid search tokens exist, early-return [] to prevent MATCH syntax errors
    if not clauses:
        return []

    try:
        safe_limit = max(1, min(int(limit), 500))
    except (ValueError, TypeError, OverflowError):
        safe_limit = 30
    match_expr = " OR ".join(clauses)

    sql = """
    SELECT e.memory_id, bm25(episodic_fts, 10.0, 1.0) AS rank_score
    FROM episodic_fts
    JOIN workspace_episodic_memory e ON episodic_fts.rowid = e.rowid
    WHERE episodic_fts MATCH :match_expr
      AND e.workspace_hash = :ws_hash
      AND e.status != 'Superseded'
    ORDER BY rank_score ASC
    LIMIT :limit;
    """

    cursor = conn.cursor()
    try:
        cursor.execute(sql, {
            "match_expr": match_expr,
            "ws_hash": workspace_hash,
            "limit": safe_limit
        })
        return cursor.fetchall()
    except sqlite3.OperationalError as oe:
        err_msg = str(oe).lower()
        if "syntax error" in err_msg:
            safe_q = persist_diag(query) if query else "[EMPTY]"
            safe_oe = persist_diag(oe)
            sys.stderr.write(f"[!] FTS5 syntax error for query '{safe_q}': {safe_oe}\n")
            return []
        raise oe


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
                sim = cosine_similarity(query_vector, query_norm, candidate_vec, stored_norm, strict=True)
                dense_scored.append((mem_id, sim))
            except Exception as e:
                import sys
                sys.stderr.write(f"[!] Warning: Dense candidate evaluation failed for {mem_id}: {e}\n")
                continue

        dense_scored.sort(key=lambda x: -x[1])
        dense_ranked_ids = [m_id for m_id, _ in dense_scored]

        # Reciprocal Rank Fusion (k=20)
        fused = reciprocal_rank_fusion(lex_ranked_ids, dense_ranked_ids, k=20, w_lex=0.5, w_dense=0.5)
        target_ids = [doc_id for doc_id, _ in fused[:top_k]]

    if not target_ids:
        return []

    # Hydrate records from workspace_episodic_memory with STRICT workspace isolation (chunked in batches of 500)
    cursor = conn.cursor()
    id_to_record = {}
    chunk_size = 500
    for i in range(0, len(target_ids), chunk_size):
        chunk = target_ids[i:i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        cursor.execute(
            f"""
            SELECT memory_id, workspace_hash, workspace_path, memory_type,
                   title, problem_signature, solution_payload, context_metadata,
                   bilingual_tags, status, activation_count, confidence_score
            FROM workspace_episodic_memory
            WHERE memory_id IN ({placeholders})
              AND workspace_hash = ?
            """,
            (*chunk, workspace_hash)
        )
        for row in cursor.fetchall():
            id_to_record[row[0]] = dict(zip(
                ["memory_id", "workspace_hash", "workspace_path", "memory_type",
                 "title", "problem_signature", "solution_payload", "context_metadata",
                 "bilingual_tags", "status", "activation_count", "confidence_score"],
                row
            ))

    # Preserve ranking order
    hydrated = [id_to_record[m_id] for m_id in target_ids if m_id in id_to_record]
    return hydrated


# ============================================================================
# Invariant Versioning & Rollback API (Argon Chốt chặn 4)
# ============================================================================

def revert_invariant(conn: sqlite3.Connection, superseded_id: str, workspace_hash: Optional[str] = None) -> bool:
    """
    Safely revert a superseded invariant back to 'Active', maintaining ACID transaction integrity.
    Follows the 3 atomic steps:
    1. Trace the chain of replacement: From superseded_id (V1), follow superseded_by to find
       the currently 'Active' record (V2 or last in chain).
    2. Demote the incorrect active record (V2) to 'Superseded' with superseded_by = NULL (prevents 2-way cycles).
    3. Re-promote V1 back to 'Active', clear superseded_by to NULL, and update last_accessed_at.
    Uses SAVEPOINT to ensure safety whether conn is inside an active caller transaction or standalone.
    Never alters conn.isolation_level directly.
    """
    cur = conn.cursor()
    caller_in_tx = getattr(conn, "in_transaction", False)
    sp_id = f"sp_rev_{uuid.uuid4().hex[:12]}"
    cur.execute(f"SAVEPOINT {sp_id};")
    try:
        # Step 1: Verify superseded_id exists and validate workspace_hash (VULN-002, VULN-006)
        if workspace_hash is not None:
            clean_rev_ws = workspace_hash.strip().lower()
            if not clean_rev_ws:
                raise ValueError("workspace_hash cannot be empty or whitespace string when supplied")
            if not is_valid_hex_hash(clean_rev_ws):
                raise ValueError(f"workspace_hash must be a 32-hex character string: '{workspace_hash}'")
            target_hash = clean_rev_ws
            cur.execute(
                "SELECT memory_id, status, superseded_by, workspace_hash FROM workspace_episodic_memory WHERE memory_id = ? AND workspace_hash = ?",
                (superseded_id, target_hash)
            )
            v1_row = cur.fetchone()
        else:
            # Query all instances to detect ambiguity and reject NULL or multiple partitions
            cur.execute(
                "SELECT workspace_hash FROM workspace_episodic_memory WHERE memory_id = ?",
                (superseded_id,)
            )
            rows = cur.fetchall()
            if len(rows) != 1 or not rows[0][0] or not str(rows[0][0]).strip():
                sys.stderr.write(f"[!] LỖI BẢO MẬT: revert_invariant called without workspace_hash and memory_id '{superseded_id}' resolves to {len(rows)} rows (ambiguous or NULL workspace_hash!)\n")
                cur.execute(f"ROLLBACK TO SAVEPOINT {sp_id};")
                cur.execute(f"RELEASE SAVEPOINT {sp_id};")
                return False
            target_hash = str(rows[0][0]).strip()
            cur.execute(
                "SELECT memory_id, status, superseded_by, workspace_hash FROM workspace_episodic_memory WHERE memory_id = ? AND workspace_hash = ?",
                (superseded_id, target_hash)
            )
            v1_row = cur.fetchone()

        if not v1_row:
            cur.execute(f"ROLLBACK TO SAVEPOINT {sp_id};")
            cur.execute(f"RELEASE SAVEPOINT {sp_id};")
            return False

        # VULN-007 / Edge Case 4: Invariant to be reverted must currently have status 'Superseded'
        if v1_row[1] != "Superseded":
            sys.stderr.write(f"[!] Warning: Cannot revert invariant {superseded_id} with status '{v1_row[1]}' (must be 'Superseded')\n")
            cur.execute(f"ROLLBACK TO SAVEPOINT {sp_id};")
            cur.execute(f"RELEASE SAVEPOINT {sp_id};")
            return False

        ws_partition = v1_row[3]

        # Trace forward to find the current 'Active' record in the replacement chain
        curr_id = v1_row[2]  # superseded_by
        active_target_id = None
        visited = {superseded_id}
        cycle_detected = False

        while curr_id:
            if curr_id in visited:
                cycle_detected = True
                break
            visited.add(curr_id)
            cur.execute(
                "SELECT memory_id, status, superseded_by FROM workspace_episodic_memory WHERE memory_id = ? AND workspace_hash = ?",
                (curr_id, ws_partition)
            )
            row = cur.fetchone()
            if not row:
                cur.execute(f"ROLLBACK TO SAVEPOINT {sp_id};")
                cur.execute(f"RELEASE SAVEPOINT {sp_id};")
                sys.stderr.write(f"[!] LỖI revert_invariant: Broken superseded_by chain at {curr_id}\n")
                return False
            if row[1] == "Active":
                active_target_id = row[0]
                break
            curr_id = row[2]

        if cycle_detected and not active_target_id:
            cur.execute(f"ROLLBACK TO SAVEPOINT {sp_id};")
            cur.execute(f"RELEASE SAVEPOINT {sp_id};")
            sys.stderr.write(f"[!] LỖI revert_invariant: Cycle detected at {curr_id} in chain\n")
            return False

        # Step 2: Demote active record (if found)
        if active_target_id:
            cur.execute(
                """
                UPDATE workspace_episodic_memory
                SET status = 'Superseded', superseded_by = ?
                WHERE memory_id = ? AND workspace_hash = ?
                """,
                (superseded_id, active_target_id, ws_partition)
            )

        # Step 3: Re-promote original record V1
        cur.execute(
            """
            UPDATE workspace_episodic_memory
            SET status = 'Active', superseded_by = NULL, last_accessed_at = datetime('now')
            WHERE memory_id = ? AND workspace_hash = ?
            """,
            (superseded_id, ws_partition)
        )

        cur.execute(f"RELEASE SAVEPOINT {sp_id};")
        # VULN-007: If caller was not in an active transaction, commit to persist; otherwise preserve caller transaction
        if not caller_in_tx:
            conn.commit()
        return True
    except Exception as e:
        try:
            cur.execute(f"ROLLBACK TO SAVEPOINT {sp_id};")
            cur.execute(f"RELEASE SAVEPOINT {sp_id};")
        except Exception:
            pass
        sys.stderr.write(f"[!] LỖI revert_invariant({superseded_id}): {type(e).__name__}: {e}\n")
        return False
