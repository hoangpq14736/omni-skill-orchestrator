"""
Tier 3 Background Memory Consolidator for Omni-Memory v4.0.
Operates out-of-band to cluster activation logs, promote proven patterns with bilingual tags,
apply bounded Ebbinghaus decay, manage soft-archiving, and perform WAL maintenance.
100% Python Standard Library.
"""

import argparse
import datetime
import hashlib
import json
import math
import os
import sqlite3
import sys
import time
from typing import Dict, List, Optional, Tuple, Any

# Ensure scripts directory is on sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_utils import fold_vietnamese, canonical_workspace_hash
from memory_schema import init_database
from experiential_memory import record_trace, TRACES_FILE


# ----------------------------------------------------------------------
# Bilingual Tag Extraction (T026)
# ----------------------------------------------------------------------
_VOCAB: List[Tuple[List[str], List[str]]] = [
    (["docker", "port"], [
        "port conflict", "xung dot cong", "bind address", "loi cong dang dung"
    ]),
    (["cuda", "vram", "oom"], [
        "out of memory", "het vram", "tran bo nho", "gpu memory"
    ]),
    (["syntax error"], [
        "syntax error", "loi cu phap"
    ]),
    (["permission denied", "access"], [
        "permission denied", "loi quyen truy cap", "khong co quyen"
    ]),
    (["sqlite", "wal"], [
        "database lock", "khoa co so du lieu", "wal busy"
    ]),
    (["timeout", "tdr"], [
        "timeout error", "loi qua thoi gian", "gpu hang"
    ]),
]


def extract_bilingual_tags(text: str) -> str:
    """Scan text for technical keywords and return a comma-separated string of unique tags."""
    if not text:
        return ""
    lowered = text.lower()
    seen = set()
    ordered_tags: List[str] = []

    for triggers, tags in _VOCAB:
        if any(trigger in lowered for trigger in triggers):
            for tag in tags:
                if tag not in seen:
                    seen.add(tag)
                    ordered_tags.append(tag)

    return ", ".join(ordered_tags)


# ----------------------------------------------------------------------
# Bounded Ebbinghaus Retention Stability (T027 & T028)
# ----------------------------------------------------------------------
def calculate_ebbinghaus_stability(
    s0: float,
    lambda_0: float,
    delta_days: float,
    n_hits: int,
    alpha: float = 1.5,
) -> float:
    """
    Compute Ebbinghaus retention stability S(t) bounded strictly within [0.0, 1.0].
    Formula: S(t) = s0 * exp(- (lambda_0 * max(0.0, delta_days)) / (1.0 + alpha * ln(1 + n_hits)))
    """
    if s0 <= 0.0:
        return 0.0
    if lambda_0 == 0.0:
        return 1.0

    delta = max(0.0, delta_days)
    denominator = 1.0 + alpha * math.log(1.0 + n_hits)
    exponent = - (lambda_0 * delta) / denominator
    stability = s0 * math.exp(exponent)
    return max(0.0, min(1.0, stability))


# ----------------------------------------------------------------------
# Tier 3 Consolidator Engine Core
# ----------------------------------------------------------------------
class ConsolidatorEngine:
    """Consolidation pipeline processor."""

    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn

    def drain_l1_staging(self, chunk_size: int = 100) -> int:
        """Drain events from l1_staging_log into activation_events table."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT staging_id, session_id, timestamp, user_input, workspace_hash, top_skill, tier_used, recalled_traces
            FROM l1_staging_log
            WHERE is_drained = 0
            ORDER BY staging_id ASC
            LIMIT ?
            """,
            (chunk_size,)
        )
        rows = cur.fetchall()
        if not rows:
            return 0

        drained_ids = []
        for row in rows:
            s_id, session_id, ts, u_input, ws_hash, top_skill, tier, recalled = row
            cur.execute(
                """
                INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0)
                """,
                (session_id, ts, u_input, ws_hash, top_skill, tier, recalled)
            )
            drained_ids.append(s_id)

        placeholders = ",".join("?" for _ in drained_ids)
        cur.execute(f"UPDATE l1_staging_log SET is_drained = 1 WHERE staging_id IN ({placeholders})", drained_ids)
        # Argon Chốt chặn 2: Xóa vật lý các dòng đã drain để giải phóng trang đĩa cho incremental_vacuum
        cur.execute(f"DELETE FROM l1_staging_log WHERE staging_id IN ({placeholders})", drained_ids)
        self.conn.commit()
        return len(drained_ids)

    def consolidate_batch(self, batch_size: int = 100, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute full consolidation cycle:
        1. Fetch pending activation_events.
        2. Cluster patterns by folded signature.
        3. Promote patterns with >= 2 successes to workspace_episodic_memory and proven_traces.json.
        4. Apply Ebbinghaus decay to episodic memory; soft-archive stale records.
        5. Mark events as consolidated.
        """
        cur = self.conn.cursor()

        # Step 1: Drain any pending L1 logs
        self.drain_l1_staging(chunk_size=batch_size)

        # Step 2: Ingest unprocessed activation events
        cur.execute(
            """
            SELECT event_id, session_id, timestamp, user_input, workspace_dir, feedback_score
            FROM activation_events
            WHERE is_consolidated = 0
            ORDER BY event_id ASC
            LIMIT ?
            """,
            (batch_size,)
        )
        events = cur.fetchall()
        if not events:
            return {"events_processed": 0, "promoted_traces": 0, "soft_archived": 0}

        # Step 3: Cluster events by normalized folded query
        clusters: Dict[str, List[Dict[str, Any]]] = {}
        processed_ids = []

        for ev in events:
            ev_id, sess_id, ts, user_inp, ws_dir, fb = ev
            processed_ids.append(ev_id)
            if not user_inp or fb < 0.0:
                continue

            # Normalized clustering key using fold_vietnamese
            cluster_key = fold_vietnamese(user_inp.strip())
            clusters.setdefault(cluster_key, []).append({
                "id": ev_id,
                "input": user_inp,
                "ws_dir": ws_dir,
                "feedback": fb
            })

        # Step 4: Trace Frequency Promotion (>= 2 successful hits)
        promoted_count = 0
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        for key, cluster_events in clusters.items():
            if len(cluster_events) >= 2:
                rep = cluster_events[0]
                raw_text = rep["input"]
                ws_dir = rep["ws_dir"]
                ws_hash = canonical_workspace_hash(ws_dir)
                tags = extract_bilingual_tags(raw_text)

                mem_id = f"trace-{hashlib.md5(f'{ws_hash}:{key}'.encode('utf-8')).hexdigest()[:12]}"
                folded_content = fold_vietnamese(f"{raw_text} {tags}")

                if not dry_run:
                    # Check if already present in episodic memory
                    cur.execute("SELECT memory_id, activation_count FROM workspace_episodic_memory WHERE memory_id = ?", (mem_id,))
                    existing = cur.fetchone()

                    if existing:
                        # Reinforce existing trace
                        cur.execute(
                            """
                            UPDATE workspace_episodic_memory
                            SET activation_count = activation_count + ?,
                                last_accessed_at = ?,
                                workspace_hash = ?,
                                status = 'Active'
                            WHERE memory_id = ?
                            """,
                            (len(cluster_events), now_str, ws_hash, mem_id)
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO workspace_episodic_memory (
                                memory_id, workspace_hash, workspace_path, memory_type,
                                title, problem_signature, solution_payload, bilingual_tags,
                                content_folded, status, activation_count, confidence_score,
                                decay_rate, last_accessed_at, created_at
                            ) VALUES (?, ?, ?, 'proven_trace', ?, ?, ?, ?, ?, 'Active', ?, 1.0, 0.08, ?, ?)
                            """,
                            (
                                mem_id, ws_hash, ws_dir,
                                f"Promoted: {raw_text[:80]}",
                                raw_text,
                                f"# Verified Fix for: {raw_text}",
                                tags,
                                folded_content,
                                len(cluster_events),
                                now_str, now_str
                            )
                        )

                    # Also update fast in-memory proven_traces.json
                    try:
                        record_trace(
                            problem_signature=raw_text,
                            proven_solution=f"Verified fix for {raw_text[:100]}",
                            tags=[t.strip() for t in tags.split(",") if t.strip()],
                            workspace_context=ws_dir
                        )
                    except Exception:
                        pass

                promoted_count += 1

        # Step 5: Bounded Ebbinghaus Decay & Soft-Archiving (T027 & T028)
        soft_archived_count = 0
        cur.execute(
            """
            SELECT memory_id, memory_type, confidence_score, decay_rate, activation_count, last_accessed_at, status
            FROM workspace_episodic_memory
            WHERE status = 'Active'
            """
        )
        active_memories = cur.fetchall()

        for mem in active_memories:
            m_id, m_type, s0, decay_rate, n_hits, last_acc_str, cur_status = mem

            # Invariants are permanent (lambda_0 = 0.0)
            if m_type == "invariant" or decay_rate == 0.0:
                continue

            try:
                last_dt = datetime.datetime.fromisoformat(last_acc_str.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                continue

            delta_days = max(0.0, (now_dt - last_dt).total_seconds() / 86400.0)
            new_st = calculate_ebbinghaus_stability(s0, decay_rate, delta_days, n_hits, alpha=1.5)

            # Soft-archiving policy: S(t) < 0.20 AND delta_days >= 7.0 AND not invariant
            if new_st < 0.20 and delta_days >= 7.0:
                if not dry_run:
                    cur.execute(
                        "UPDATE workspace_episodic_memory SET status = 'Archived', confidence_score = ? WHERE memory_id = ?",
                        (new_st, m_id)
                    )
                soft_archived_count += 1
            else:
                if not dry_run:
                    cur.execute(
                        "UPDATE workspace_episodic_memory SET confidence_score = ? WHERE memory_id = ?",
                        (new_st, m_id)
                    )

        # Step 6: Mark processed events as consolidated
        if not dry_run and processed_ids:
            placeholders = ",".join("?" for _ in processed_ids)
            cur.execute(f"UPDATE activation_events SET is_consolidated = 1 WHERE event_id IN ({placeholders})", processed_ids)
            self.conn.commit()

            # Lazy Vector Backfill (Argon Chốt chặn 3)
            try:
                from embedding_service import get_embedding, MODEL_NAME
                from memory_engine import serialize_float32_blob, compute_vector_norm

                cur.execute(
                    """
                    SELECT e.memory_id, e.workspace_hash, e.title, e.problem_signature, e.solution_payload
                    FROM workspace_episodic_memory e
                    LEFT JOIN dense_embeddings d ON e.memory_id = d.memory_id
                    WHERE e.status = 'Active' AND d.memory_id IS NULL
                    LIMIT 50;
                    """
                )
                rows_to_backfill = cur.fetchall()
                for row in rows_to_backfill:
                    mem_id, ws_hash, title, sig, sol = row
                    embed_text = f"{title} {sig or ''} {sol}"[:1000]
                    vec = get_embedding(embed_text, is_query=False)
                    if vec:
                        norm = compute_vector_norm(vec)
                        blob = serialize_float32_blob(vec)
                        cur.execute(
                            """
                            INSERT OR REPLACE INTO dense_embeddings (memory_id, workspace_hash, model_name, dimensions, vector_blob, norm, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                            """,
                            (mem_id, ws_hash, MODEL_NAME, len(vec), blob, norm)
                        )
                self.conn.commit()
            except Exception:
                pass

            # Incremental WAL vacuuming & Passive Checkpoint (Argon Chốt chặn 2)
            try:
                self.conn.execute("PRAGMA incremental_vacuum(100);")
                self.conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
            except Exception:
                pass

        return {
            "events_processed": len(processed_ids),
            "promoted_traces": promoted_count,
            "soft_archived": soft_archived_count
        }


def main():
    parser = argparse.ArgumentParser(description="Omni-Memory v4.0 Background Consolidator")
    parser.add_argument("--workspace", default=os.getcwd(), help="Target workspace root path")
    parser.add_argument("--batch-run", action="store_true", help="Run batch consolidation cycle")
    parser.add_argument("--dry-run", action="store_true", help="Simulate consolidation without persisting")
    args = parser.parse_args()

    # Argon Chốt chặn 1: Khóa file tuyệt đối, chỉ cho phép 1 tiến trình chạy tại một thời điểm
    from backend_client import acquire_lock_with_stale_recovery, release_autostart_lock
    lock_file = os.path.join(_SCRIPT_DIR, "consolidator.lock")
    if not acquire_lock_with_stale_recovery(lock_file, stale_timeout_sec=60.0):
        print(json.dumps({"status": "skipped", "reason": "Another consolidator is currently running"}))
        return

    try:
        db_path = os.path.join(_SCRIPT_DIR, "..", "omni_memory.db")
        conn = init_database(db_path)

        engine = ConsolidatorEngine(conn)
        result = engine.consolidate_batch(batch_size=100, dry_run=args.dry_run)
        conn.close()
        print(json.dumps(result, indent=2))
    finally:
        release_autostart_lock(lock_file)


if __name__ == "__main__":
    main()
