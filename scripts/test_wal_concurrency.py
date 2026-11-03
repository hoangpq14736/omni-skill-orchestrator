#!/usr/bin/env python3
"""
High-Pressure Multi-Process Concurrency Stress Test on SQLite WAL.
Proves 1000+ QPS without database locking or corruption on Windows NTFS.

Simulates 3 Concurrent Real OS Processes:
1. Actor 1 (Hook Ingestion): High-frequency INSERTs into l1_staging_log.
2. Actor 2 (Consolidator Engine): Continuous batch SELECT, UPDATE, and PRAGMA wal_checkpoint(PASSIVE).
3. Actor 3 (L2 Memory Retrieval): High-speed dual-column BM25 FTS5 full-text queries.

Uses concurrent.futures.ProcessPoolExecutor (Real multiprocessing across CPU cores).
"""

import os
import sys
import time
import uuid
import random
import sqlite3
import tempfile
import shutil
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Any

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_schema import init_database
from memory_utils import fold_vietnamese


# ----------------------------------------------------------------------
# Actor 1: High-Speed L1 Hook Ingestion (Writer)
# ----------------------------------------------------------------------
def actor_hook_writer(db_path: str, duration_sec: float) -> Dict[str, Any]:
    """Actor 1: Simulates hook_runner.py rapidly staging incoming telemetry."""
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    writes = 0
    locked_errors = 0
    other_errors = 0
    start = time.time()

    skills = ["spec-driven-development", "omni-skill-orchestrator", "skill-arbiter", "python-testing"]
    queries = [
        "cần fix bug sqlite database lock",
        "tối ưu hóa memory retrieval FTS5",
        "triển khai docker compose postgres",
        "debug out of memory vram cuda"
    ]

    while time.time() - start < duration_sec:
        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        u_input = random.choice(queries)
        skill = random.choice(skills)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            conn.execute(
                """
                INSERT INTO l1_staging_log (
                    session_id, timestamp, user_input, workspace_hash, top_skill, tier_used, recalled_traces, is_drained
                ) VALUES (?, ?, ?, 'ws-a37db9ae74c8', ?, 'L1', '[]', 0)
                """,
                (session_id, now_str, u_input, skill)
            )
            conn.commit()
            writes += 1
        except sqlite3.OperationalError as oe:
            if "database is locked" in str(oe).lower() or "busy" in str(oe).lower():
                locked_errors += 1
            else:
                other_errors += 1
        except Exception:
            other_errors += 1

    conn.close()
    return {
        "actor": "Hook Writer",
        "writes": writes,
        "locked_errors": locked_errors,
        "other_errors": other_errors,
        "elapsed": time.time() - start
    }


# ----------------------------------------------------------------------
# Actor 2: Consolidator Batch Processor & WAL Checkpointer (Reader & Writer)
# ----------------------------------------------------------------------
def actor_consolidator_updater(db_path: str, duration_sec: float) -> Dict[str, Any]:
    """Actor 2: Simulates consolidator.py draining staging, updating episodic records, and WAL checkpointing."""
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    consolidations = 0
    checkpoints = 0
    locked_errors = 0
    other_errors = 0
    start = time.time()

    cycle = 0
    while time.time() - start < duration_sec:
        cycle += 1
        try:
            # Step 1: Read pending staging rows
            cur = conn.cursor()
            cur.execute("SELECT staging_id FROM l1_staging_log WHERE is_drained = 0 LIMIT 25")
            rows = cur.fetchall()

            if rows:
                ids = [r[0] for r in rows]
                placeholders = ",".join("?" for _ in ids)

                # Step 2: Mark drained and delete from staging
                conn.execute(f"UPDATE l1_staging_log SET is_drained = 1 WHERE staging_id IN ({placeholders})", ids)
                conn.execute(f"DELETE FROM l1_staging_log WHERE staging_id IN ({placeholders})", ids)

                # Step 3: Update episodic memory activation count
                conn.execute(
                    """
                    UPDATE workspace_episodic_memory 
                    SET activation_count = activation_count + ?, last_accessed_at = datetime('now')
                    WHERE memory_id = 'seed-mem-1'
                    """,
                    (len(ids),)
                )
                conn.commit()
                consolidations += len(ids)

            # Step 4: Periodic PASSIVE checkpoint & incremental vacuum (every 10 cycles)
            if cycle % 10 == 0:
                conn.execute("PRAGMA incremental_vacuum(50);")
                conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
                checkpoints += 1

        except sqlite3.OperationalError as oe:
            if "database is locked" in str(oe).lower() or "busy" in str(oe).lower():
                locked_errors += 1
            else:
                other_errors += 1
        except Exception:
            other_errors += 1

        time.sleep(0.005)  # 5ms cadence matching consolidator batch pause

    conn.close()
    return {
        "actor": "Consolidator Updater",
        "consolidations": consolidations,
        "checkpoints": checkpoints,
        "locked_errors": locked_errors,
        "other_errors": other_errors,
        "elapsed": time.time() - start
    }


# ----------------------------------------------------------------------
# Actor 3: High-Speed Dual-Column FTS5 Search (Reader)
# ----------------------------------------------------------------------
def actor_fts_reader(db_path: str, duration_sec: float) -> Dict[str, Any]:
    """Actor 3: Simulates resolver.py executing high-speed dual-column BM25 full-text queries."""
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    reads = 0
    locked_errors = 0
    other_errors = 0
    start = time.time()

    search_terms = ["sqlite", "lock", "memory", "vram", "docker", "python", "kernel", "fix"]

    while time.time() - start < duration_sec:
        term = random.choice(search_terms)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT rowid, bm25(episodic_fts, 10.0, 1.0) as rank
                FROM episodic_fts
                WHERE episodic_fts MATCH ?
                ORDER BY rank ASC
                LIMIT 10
                """,
                (term,)
            )
            _ = cur.fetchall()
            reads += 1
        except sqlite3.OperationalError as oe:
            if "database is locked" in str(oe).lower() or "busy" in str(oe).lower():
                locked_errors += 1
            else:
                other_errors += 1
        except Exception:
            other_errors += 1

    conn.close()
    return {
        "actor": "FTS Reader",
        "reads": reads,
        "locked_errors": locked_errors,
        "other_errors": other_errors,
        "elapsed": time.time() - start
    }


# ----------------------------------------------------------------------
# Test Orchestration & Verification Harness
# ----------------------------------------------------------------------
def seed_test_database(db_path: str):
    """Initializes schema and seeds episodic memory for FTS5 queries."""
    conn = init_database(db_path)
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    seeds = [
        ("seed-mem-1", "Fix SQLite WAL database locked error", "Handle SQLite WAL locking with PRAGMA busy_timeout = 5000 and synchronous = NORMAL.", "sqlite, wal, database lock, khoa co so du lieu"),
        ("seed-mem-2", "Docker port conflict resolution", "Use netstat or ss to identify process occupying port and kill or rebind.", "docker, port conflict, xung dot cong"),
        ("seed-mem-3", "CUDA VRAM Out of Memory mitigation", "Clear PyTorch cache with torch.cuda.empty_cache() and reduce batch size.", "cuda, vram, out of memory, het vram"),
        ("seed-mem-4", "Omni-Kernel sub-millisecond reflex", "Module-level compiled regex and Python stdlib cache to achieve sub-0.1ms.", "kernel, reflex, sub-millisecond, python"),
        ("seed-mem-5", "Memory FTS5 Dual Column BM25 Ranking", "Exact content column weighted 10.0 and folded column weighted 1.0.", "memory, fts5, bm25, ranking")
    ]

    for m_id, title, sol, tags in seeds:
        folded = fold_vietnamese(f"{title} {sol} {tags}")
        conn.execute(
            """
            INSERT OR REPLACE INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type, title,
                problem_signature, solution_payload, bilingual_tags, content_folded,
                status, activation_count, confidence_score, decay_rate, last_accessed_at, created_at
            ) VALUES (?, 'ws-a37db9ae74c8', 'd:/Antigravity/Skill management', 'proven_trace', ?, ?, ?, ?, ?, 'Active', 5, 1.0, 0.08, ?, ?)
            """,
            (m_id, title, title, sol, tags, folded, now_str, now_str)
        )

    conn.commit()
    conn.close()


def run_concurrency_stress_test(duration_sec: float = 10.0):
    temp_dir = tempfile.mkdtemp()
    test_db = os.path.join(temp_dir, "test_omni_memory.db")

    print(f"\n🚀 STARTING 3-PROCESS SQLITE WAL CONCURRENCY STRESS TEST ({duration_sec}s)...")
    print(f"Target DB: {test_db}")

    try:
        seed_test_database(test_db)

        # Run 3 distinct OS processes concurrently
        with ProcessPoolExecutor(max_workers=3) as executor:
            fut_writer = executor.submit(actor_hook_writer, test_db, duration_sec)
            fut_consolidator = executor.submit(actor_consolidator_updater, test_db, duration_sec)
            fut_reader = executor.submit(actor_fts_reader, test_db, duration_sec)

            res_writer = fut_writer.result()
            res_consolidator = fut_consolidator.result()
            res_reader = fut_reader.result()

        # Aggregate metrics
        total_ops = res_writer["writes"] + res_consolidator["consolidations"] + res_reader["reads"]
        total_locks = res_writer["locked_errors"] + res_consolidator["locked_errors"] + res_reader["locked_errors"]
        total_other = res_writer["other_errors"] + res_consolidator["other_errors"] + res_reader["other_errors"]
        overall_qps = total_ops / duration_sec

        print("\n" + "=" * 65)
        print("📊 STRESS TEST RESULTS (Multi-Process Concurrency on Windows NTFS)")
        print("=" * 65)
        print(f"1. Actor 1 (Hook Writer)       : {res_writer['writes']:,} INSERTs (Locks: {res_writer['locked_errors']})")
        print(f"2. Actor 2 (Consolidator)      : {res_consolidator['consolidations']:,} Rows Drained, {res_consolidator['checkpoints']} WAL Checkpoints (Locks: {res_consolidator['locked_errors']})")
        print(f"3. Actor 3 (FTS Reader)        : {res_reader['reads']:,} BM25 Searches (Locks: {res_reader['locked_errors']})")
        print("-" * 65)
        print(f"Total Operations Executed     : {total_ops:,} ops in {duration_sec:.1f}s")
        print(f"Throughput                    : {overall_qps:,.1f} QPS")
        print(f"Database Locked Errors        : {total_locks} (Goal: 0)")
        print(f"Other Unhandled Errors        : {total_other}")
        print("=" * 65)

        # Verify DB integrity
        conn = sqlite3.connect(test_db)
        check = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        conn.close()
        print(f"Database Integrity Check       : {check.upper()}")

        assert total_locks == 0, f"Stress test FAILED: {total_locks} 'database is locked' errors encountered!"
        assert total_other == 0, f"Stress test FAILED: {total_other} other unhandled errors encountered!"
        assert res_reader["reads"] > 500, f"FTS Reader executed insufficient searches: {res_reader['reads']}"
        assert check.lower() == "ok", f"Integrity check failed: {check}"
        assert overall_qps > 1000, f"Throughput {overall_qps} QPS below 1000 target!"
        print("\n✔ SQLite WAL Multi-Process Concurrency Stress Test PASSED with ZERO LOCKS!")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    duration = 10.0
    if len(sys.argv) > 1:
        try:
            duration = float(sys.argv[1])
        except ValueError:
            pass
    run_concurrency_stress_test(duration)
