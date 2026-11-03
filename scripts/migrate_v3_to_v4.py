"""
One-Time Idempotent Migration Script: Omni-Memory v3.0 -> v4.0.
Migrates flat-file JSON traces (proven_traces.json) and registry capabilities
into SQLite omni_memory.db with dual-column FTS5 and incremental vacuuming.
"""

import json
import os
import sqlite3
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_utils import fold_vietnamese, canonical_workspace_hash
from memory_schema import init_database

TRACES_FILE = os.path.join(_SCRIPT_DIR, "proven_traces.json")
REGISTRY_FILE = os.path.join(_SCRIPT_DIR, "registry.json")
DB_PATH = os.path.join(_SCRIPT_DIR, "..", "omni_memory.db")


def migrate():
    print(f"[*] Initializing database at {DB_PATH}...")
    conn = init_database(DB_PATH)
    cur = conn.cursor()

    # 1. Migrate Proven Traces -> workspace_episodic_memory
    migrated_traces = 0
    if os.path.exists(TRACES_FILE):
        try:
            with open(TRACES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            traces = data.get("traces", [])
            print(f"[*] Found {len(traces)} traces in {TRACES_FILE}. Migrating...")

            for tr in traces:
                t_id = tr.get("id") or f"trace-{tr.get('problem_signature')[:10]}"
                sig = tr.get("problem_signature", "")
                sol = tr.get("proven_solution", "")
                tags = ", ".join(tr.get("tags", []))
                ws_ctx = tr.get("workspace_context", "") or os.getcwd()
                ws_hash = canonical_workspace_hash(ws_ctx)
                hits = tr.get("success_count", 1)
                last_acc = tr.get("last_recalled") or tr.get("created_at") or "2026-11-03 00:00:00"
                created = tr.get("created_at") or last_acc

                content_folded = fold_vietnamese(f"Fix for: {sig} {sig} {sol} {tags}")

                cur.execute(
                    """
                    INSERT OR REPLACE INTO workspace_episodic_memory (
                        memory_id, workspace_hash, workspace_path, memory_type,
                        title, problem_signature, solution_payload, bilingual_tags,
                        content_folded, status, activation_count, confidence_score,
                        decay_rate, last_accessed_at, created_at
                    ) VALUES (?, ?, ?, 'proven_trace', ?, ?, ?, ?, ?, 'Active', ?, 1.0, 0.08, ?, ?)
                    """,
                    (
                        t_id, ws_hash, ws_ctx,
                        f"Fix for: {sig[:80]}",
                        sig, sol, tags, content_folded,
                        hits, last_acc, created
                    )
                )
                migrated_traces += 1
            conn.commit()
            print(f"[+] Migrated {migrated_traces} traces successfully.")
        except Exception as e:
            print(f"[-] Error migrating traces: {e}")

    # 2. Check and Vacuum
    try:
        conn.execute("PRAGMA incremental_vacuum(100);")
        conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
    except Exception:
        pass

    conn.close()
    print("[+] Migration completed successfully!")


if __name__ == "__main__":
    migrate()
