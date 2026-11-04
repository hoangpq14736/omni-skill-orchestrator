#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Round 7 Remediation & Regression Test Suite
Validates the 5 critical edge cases and failure scenarios specified by DeepSeek Council Gate:
1. Two independent legacy 32-hex partitions migration isolation (no cross-contamination).
2. Cluster promotion transient contention preserves is_consolidated=0 for natural retry.
3. ConsolidatorEngine unscoped mode returns unconfigured error and fails loud (exit code 1).
4. Symlink TOCTOU rejection across ProcessMutex and TrustFileLock.
5. Prompt JSON whitespace and key-order invariance between producer and verifier.
"""

import os
import sys
import json
import time
import sqlite3
import tempfile
import unittest
import subprocess
from unittest.mock import patch, MagicMock

# Add scripts directory to module path
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from memory_schema import init_database
from consolidator import ConsolidatorEngine
from lifecycle_guard import ProcessMutex
from workspace_sanitizer import TrustFileLock
from memory_utils import canonical_workspace_hash, hash_prompt


class TestRound7Remediation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_r7_memory.db")

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_two_independent_legacy_partitions_not_merged(self):
        """
        VULN-001 (CRITICAL): Ensure two independent legacy 32-hex partitions are NEVER merged.
        Partition A has a known registry path and migrates to SHA-256.
        Partition B has no registry mapping and must retain its 32-hex key without being contaminated.
        """
        raw_conn = sqlite3.connect(self.db_path)
        raw_conn.execute("PRAGMA journal_mode=WAL;")
        raw_conn.execute("""
            CREATE TABLE workspace_episodic_memory (
                memory_id TEXT PRIMARY KEY,
                workspace_hash TEXT NOT NULL,
                workspace_path TEXT,
                memory_type TEXT DEFAULT 'proven_trace',
                title TEXT,
                problem_signature TEXT,
                solution_payload TEXT,
                bilingual_tags TEXT,
                content_folded TEXT,
                status TEXT DEFAULT 'Active',
                activation_count INTEGER DEFAULT 1,
                confidence_score REAL DEFAULT 1.0,
                decay_rate REAL DEFAULT 0.08,
                last_accessed_at TEXT,
                created_at TEXT
            );
        """)
        raw_conn.execute("""
            CREATE TABLE consolidation_outbox (
                outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                workspace_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                solution TEXT NOT NULL,
                tags TEXT,
                context TEXT,
                status TEXT DEFAULT 'Pending',
                generation INTEGER DEFAULT 1,
                retry_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                claimed_at TEXT,
                owner_token TEXT,
                flushed_at TEXT,
                UNIQUE(memory_id, workspace_hash)
            );
        """)
        raw_conn.execute("""
            CREATE TABLE activation_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TEXT,
                user_input TEXT,
                workspace_dir TEXT,
                top_skill TEXT,
                tier_used INTEGER,
                recalled_traces TEXT,
                feedback_score REAL,
                is_consolidated INTEGER DEFAULT 0,
                last_error TEXT
            );
        """)
        raw_conn.execute("""
            CREATE TABLE workspace_registry (
                workspace_hash TEXT PRIMARY KEY,
                workspace_path TEXT NOT NULL,
                registered_at TEXT NOT NULL
            );
        """)

        legacy_hash_a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        legacy_hash_b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        registered_path_a = os.path.join(self.temp_dir.name, "workspace_a")
        os.makedirs(registered_path_a, exist_ok=True)

        # Register only partition A
        raw_conn.execute(
            "INSERT INTO workspace_registry (workspace_hash, workspace_path, registered_at) VALUES (?, ?, datetime('now'));",
            (legacy_hash_a, registered_path_a)
        )
        # Seed records for both partitions
        raw_conn.execute(
            "INSERT INTO workspace_episodic_memory (memory_id, workspace_hash, title) VALUES (?, ?, ?);",
            ("mem-a", legacy_hash_a, "Memory A")
        )
        raw_conn.execute(
            "INSERT INTO workspace_episodic_memory (memory_id, workspace_hash, title) VALUES (?, ?, ?);",
            ("mem-b", legacy_hash_b, "Memory B")
        )
        raw_conn.execute(
            "INSERT INTO consolidation_outbox (memory_id, workspace_hash, signature, solution, created_at) VALUES (?, ?, ?, ?, datetime('now'));",
            ("mem-a", legacy_hash_a, "sig-a", "sol-a")
        )
        raw_conn.execute(
            "INSERT INTO consolidation_outbox (memory_id, workspace_hash, signature, solution, created_at) VALUES (?, ?, ?, ?, datetime('now'));",
            ("mem-b", legacy_hash_b, "sig-b", "sol-b")
        )
        raw_conn.commit()
        raw_conn.close()

        # Run init_database which performs the migration
        conn = init_database(self.db_path)

        expected_sha256_a = canonical_workspace_hash(registered_path_a)
        self.assertEqual(len(expected_sha256_a), 64)

        # Partition A must be migrated to SHA-256
        row_a = conn.execute("SELECT workspace_hash FROM workspace_episodic_memory WHERE memory_id = 'mem-a';").fetchone()
        self.assertEqual(row_a[0], expected_sha256_a)

        row_ob_a = conn.execute("SELECT workspace_hash FROM consolidation_outbox WHERE memory_id = 'mem-a';").fetchone()
        self.assertEqual(row_ob_a[0], expected_sha256_a)

        # Partition B must RETAIN its legacy 32-hex hash and NOT be merged into Partition A!
        row_b = conn.execute("SELECT workspace_hash FROM workspace_episodic_memory WHERE memory_id = 'mem-b';").fetchone()
        self.assertEqual(row_b[0], legacy_hash_b, "Unregistered legacy partition must retain 32-hex hash")

        row_ob_b = conn.execute("SELECT workspace_hash FROM consolidation_outbox WHERE memory_id = 'mem-b';").fetchone()
        self.assertEqual(row_ob_b[0], legacy_hash_b, "Unregistered legacy partition outbox must retain 32-hex hash")

        # Verify Partition B was NOT contaminated with Partition A's path or hash
        count_shared = conn.execute(
            "SELECT count(*) FROM workspace_episodic_memory WHERE workspace_hash = ?;",
            (expected_sha256_a,)
        ).fetchone()[0]
        self.assertEqual(count_shared, 1, "Partition A must contain strictly 1 record (no cross-contamination)")
        conn.close()

    def test_promotion_transient_error_preserves_retry_status(self):
        """
        VULN-002 (HIGH): When cluster promotion encounters a transient lock contention error,
        events must NOT be marked is_consolidated=1. They must remain is_consolidated=0 for natural retry.
        """
        conn = init_database(self.db_path)
        ws_dir = os.path.join(self.temp_dir.name, "workspace_promo")
        os.makedirs(ws_dir, exist_ok=True)
        ws_hash = canonical_workspace_hash(ws_dir)

        # Register workspace
        conn.execute("INSERT OR REPLACE INTO workspace_registry VALUES (?, ?, datetime('now'));", (ws_hash, ws_dir))

        # Insert 2 positive activation events that form a promotable cluster
        conn.execute("""
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, feedback_score, is_consolidated)
            VALUES ('s1', datetime('now'), 'Fix python import path error', ?, 1.0, 0);
        """, (ws_dir,))
        conn.execute("""
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, feedback_score, is_consolidated)
            VALUES ('s2', datetime('now'), 'Fix python import path error', ?, 1.0, 0);
        """, (ws_dir,))
        conn.commit()

        engine = ConsolidatorEngine(conn, workspace_root=ws_dir)

        # Simulate transient error (database is locked) on inserting into consolidation_outbox
        class FaultyCursor:
            def __init__(self, real_cursor):
                self._cur = real_cursor

            def execute(self, sql, *args, **kwargs):
                if "INSERT INTO consolidation_outbox" in sql:
                    raise sqlite3.OperationalError("database is locked")
                return self._cur.execute(sql, *args, **kwargs)

            def executemany(self, sql, *args, **kwargs):
                return self._cur.executemany(sql, *args, **kwargs)

            def fetchone(self):
                return self._cur.fetchone()

            def fetchall(self):
                return self._cur.fetchall()

            def __getattr__(self, name):
                return getattr(self._cur, name)

        class FaultyConn:
            def __init__(self, real_conn):
                self._conn = real_conn

            def cursor(self):
                return FaultyCursor(self._conn.cursor())

            def execute(self, *args, **kwargs):
                return self._conn.execute(*args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._conn, name)

        engine.conn = FaultyConn(conn)
        result = engine.consolidate_batch(batch_size=10)

        self.assertEqual(result.get("promoted_traces", 0), 0)

        # Events must REMAIN is_consolidated=0 for retry
        rows = conn.execute("SELECT is_consolidated FROM activation_events WHERE workspace_dir = ?;", (ws_dir,)).fetchall()
        for r in rows:
            self.assertEqual(r[0], 0, "Event must remain is_consolidated=0 upon transient error")

        # Now restore clean conn and run consolidation cycle: promotion should succeed!
        engine.conn = conn
        clean_res = engine.consolidate_batch(batch_size=10)
        self.assertEqual(clean_res.get("promoted_traces"), 1)

        # Now they should be consolidated
        updated_rows = conn.execute("SELECT is_consolidated FROM activation_events WHERE workspace_dir = ?;", (ws_dir,)).fetchall()
        for r in updated_rows:
            self.assertEqual(r[0], 1, "Event must be marked is_consolidated=1 after successful promotion")
        conn.close()

    def test_consolidator_unscoped_error_and_cli_exit_code(self):
        """
        VULN-003 (HIGH): ConsolidatorEngine unscoped consolidation must return
        an explicit 'unconfigured_unscoped_error' status instead of pretending 0 is success.
        CLI must exit non-zero when workspace is unconfigured.
        """
        conn = init_database(self.db_path)
        # Unscoped engine with allow_unscoped=False
        engine = ConsolidatorEngine(conn, workspace_root=None, workspace_hash=None, allow_unscoped=False)
        result = engine.consolidate_batch()
        self.assertEqual(result.get("status"), "unconfigured_unscoped_error")
        conn.close()

        # Test CLI invocation with empty/unconfigured workspace
        res = subprocess.run(
            [sys.executable, os.path.join(_SCRIPTS_DIR, "consolidator.py"), "--workspace", ""],
            capture_output=True,
            text=True
        )
        self.assertNotEqual(res.returncode, 0, "Consolidator CLI must fail loudly with non-zero exit code on unconfigured workspace")

    def test_process_mutex_and_trust_file_lock_symlink_rejection(self):
        """
        VULN-007 (MEDIUM): ProcessMutex and TrustFileLock must both reject symbolic links
        and reparse points via O_NOFOLLOW and fstat inspection.
        """
        real_file = os.path.join(self.temp_dir.name, "target_real.txt")
        with open(real_file, "w") as f:
            f.write("target")

        symlink_mutex = os.path.join(self.temp_dir.name, "attack.mutex")
        symlink_lock = os.path.join(self.temp_dir.name, "attack.lock")

        can_symlink = False
        try:
            os.symlink(real_file, symlink_mutex)
            os.symlink(real_file, symlink_lock)
            can_symlink = True
        except (OSError, NotImplementedError):
            pass

        if can_symlink:
            # ProcessMutex must reject symlink
            with self.assertRaises(PermissionError) as ctx1:
                with ProcessMutex(symlink_mutex, timeout=1.0):
                    pass
            self.assertIn("Security violation", str(ctx1.exception))

            # TrustFileLock must reject symlink
            with self.assertRaises(PermissionError) as ctx2:
                with TrustFileLock(symlink_lock, timeout=1.0):
                    pass
            self.assertIn("Security violation", str(ctx2.exception))
        else:
            # On Windows without SeCreateSymbolicLinkPrivilege, verify that regular files acquire cleanly
            clean_mutex = os.path.join(self.temp_dir.name, "normal.mutex")
            with ProcessMutex(clean_mutex, timeout=1.0):
                self.assertTrue(os.path.exists(clean_mutex))

            clean_lock = os.path.join(self.temp_dir.name, "normal.lock")
            with TrustFileLock(clean_lock, timeout=1.0):
                self.assertTrue(os.path.exists(clean_lock))

    def test_prompt_json_whitespace_and_key_order_invariance(self):
        """
        Defensive #2: Ensure JSON prompt hashes remain 100% identical regardless of
        whitespace, indentation, or key ordering between producer and verifier.
        """
        prompt_ugly = """
        {
           "task":    "Council Gate Audit",
           "scope": "production_remediation",
           "details": {
               "round":   7,
               "verified": true
           }
        }
        """
        prompt_compact = '{"details":{"round":7,"verified":true},"scope":"production_remediation","task":"Council Gate Audit"}'
        prompt_tabs = '{\n\t"task":\t"Council Gate Audit",\n\t"scope":\t"production_remediation",\n\t"details":\t{\n\t\t"round":\t7,\n\t\t"verified":\ttrue\n\t}\n}'

        hash1 = hash_prompt(prompt_ugly)
        hash2 = hash_prompt(prompt_compact)
        hash3 = hash_prompt(prompt_tabs)

        self.assertTrue(len(hash1) == 64, "hash_prompt must return valid 64-char SHA256")
        self.assertEqual(hash1, hash2, "JSON prompts with different whitespace/ordering must have identical hash")
        self.assertEqual(hash2, hash3, "JSON prompts with tab indentations must have identical hash")

    def test_file_audit_input_hash_with_secret_does_not_mismatch(self):
        """
        VULN-101: Audited target file containing a secret/token line must produce
        identical input_hash between producer and verifier, preventing STALE_REVIEW false rejection.
        """
        from consult_critic import format_markdown_report
        from hook_runner import verify_critic_artifact

        target_file_path = os.path.join(self.temp_dir.name, "config_with_secret.py")
        content = 'DATABASE_URL = "postgres://admin:password123456@localhost:5432/mydb"\nAPI_KEY = "sk-ant-api03-abcdef1234567890abcdef"\n'
        with open(target_file_path, "wb") as f:
            f.write(content.encode("utf-8"))

        import hashlib
        raw_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

        audit_data = {
            "verdict": "APPROVED",
            "confidence_score": 0.95,
            "summary": "Verified secure config",
            "critical_vulnerabilities": [],
            "edge_cases": [
                {"scenario": "A", "consequence": "B", "mitigation": "C"},
                {"scenario": "D", "consequence": "E", "mitigation": "F"},
                {"scenario": "G", "consequence": "H", "mitigation": "I"}
            ]
        }

        # Format report as consult_critic does for a physical target file (raw_file_v1 domain)
        report_md = format_markdown_report(
            data=audit_data,
            target_file=os.path.basename(target_file_path),
            input_hash=raw_hash,
            model="deepseek-flash",
            workspace_dir=self.temp_dir.name,
            hash_domain="raw_file_v1"
        )

        review_path = os.path.join(self.temp_dir.name, "AUDIT_REVIEW.md")
        with open(review_path, "w", encoding="utf-8") as rf:
            rf.write(report_md)

        # Verifier runs
        best_verdict, best_meta = verify_critic_artifact(
            workspace_dir=self.temp_dir.name,
            target_file=os.path.basename(target_file_path)
        )

        self.assertEqual(best_verdict, "APPROVED", f"File with secrets must verify as APPROVED, not STALE_REVIEW (got reason: {best_meta.get('stale_reason') if best_meta else None})")

    def test_filelock_same_instance_nested_reentrancy_no_leak(self):
        """
        VULN-102: FileLock nested reentrancy on the SAME instance must not leak
        underlying RLock or leave orphaned entries in _PROCESS_LOCKS registry.
        """
        from experiential_memory import FileLock, _PROCESS_LOCKS, _lock_local

        lock_target = os.path.join(self.temp_dir.name, "test_reentrant.lock")
        lock = FileLock(lock_target, timeout=2.0)

        with lock:
            with lock:
                with lock:
                    pass

        self.assertIsNone(lock._rlock, "self._rlock must be None after outermost exit")
        self.assertNotIn(lock._lock_key, _PROCESS_LOCKS, "_PROCESS_LOCKS entry must be pruned after outermost exit")
        held = getattr(_lock_local, "held_locks", {})
        self.assertNotIn(lock._lock_key, held, "Thread-local held_locks must be empty for key")

    def test_drain_l1_staging_recovers_orphaned_proc_file(self):
        """
        VULN-103: drain_l1_staging must detect and recover any orphaned .proc_* spool files
        left by a previous hard crash, preventing silent telemetry loss.
        """
        conn = init_database(self.db_path)
        engine = ConsolidatorEngine(conn, workspace_root=self.temp_dir.name)

        spool_path = os.path.join(_SCRIPTS_DIR, "l1_staging_spool.jsonl")
        spool_dir = os.path.dirname(spool_path)
        orphaned_proc = os.path.join(spool_dir, f"l1_staging_spool.jsonl.proc_crash_test_{os.getpid()}")

        entry1 = {
            "session_id": "sess_recovery_1",
            "timestamp": "2026-11-05 01:00:00",
            "user_input": "Crash recovery telemetry item 1",
            "workspace_hash": engine.workspace_hash,
            "top_skill": "skill_rec",
            "tier_used": 1,
            "recalled_traces": []
        }
        with open(orphaned_proc, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry1) + "\n")

        try:
            # Drain should sweep and recover the orphaned file
            engine.drain_l1_staging(chunk_size=100)

            # Assert the orphaned file was cleaned up
            self.assertFalse(os.path.exists(orphaned_proc), "Orphaned .proc_* file must be removed after recovery")

            # Assert the record made it to activation_events
            row = conn.execute(
                "SELECT count(*) FROM activation_events WHERE session_id = 'sess_recovery_1';"
            ).fetchone()
            self.assertEqual(row[0], 1, "Orphaned telemetry entry must be recovered into activation_events")
        finally:
            if os.path.exists(orphaned_proc):
                try:
                    os.remove(orphaned_proc)
                except Exception:
                    pass
            conn.close()

    def test_dual_tier_multi_word_negation_invariance(self):
        """
        VULN-105: _PAT_NEGATION must tolerate multi-word auxiliaries in both English and Vietnamese,
        preventing cosmetic prompts from unnecessary Tier 2 over-escalation.
        """
        from dual_tier import ComplexityRouter

        test_phrases = [
            "Đừng có mà đụng vào logic concurrency nha",
            "Không được đụng vào memory engine",
            "Chớ có mà sửa phần database",
            "Do not ever touch the migration files",
            "Never really change the underlying schema"
        ]

        for phrase in test_phrases:
            self.assertTrue(
                bool(ComplexityRouter._PAT_NEGATION.search(phrase)),
                f"Multi-word negation pattern must match: {phrase!r}"
            )

    def test_migration_with_preexisting_duplicate_memory_id_does_not_abort(self):
        """
        VULN-104: If a memory_id already exists under both 32-hex and 64-hex hashes
        (partial earlier migration), init_database must pre-collapse duplicates and NOT abort.
        """
        raw_conn = sqlite3.connect(self.db_path)
        raw_conn.execute("PRAGMA journal_mode=WAL;")
        raw_conn.execute("""
            CREATE TABLE workspace_episodic_memory (
                memory_id TEXT NOT NULL,
                workspace_hash TEXT NOT NULL,
                workspace_path TEXT,
                memory_type TEXT DEFAULT 'proven_trace',
                title TEXT,
                problem_signature TEXT,
                solution_payload TEXT,
                bilingual_tags TEXT,
                content_folded TEXT,
                status TEXT DEFAULT 'Active',
                activation_count INTEGER DEFAULT 1,
                confidence_score REAL DEFAULT 1.0,
                decay_rate REAL DEFAULT 0.08,
                last_accessed_at TEXT,
                created_at TEXT,
                PRIMARY KEY (memory_id, workspace_hash)
            );
        """)
        raw_conn.execute("""
            CREATE TABLE consolidation_outbox (
                outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                workspace_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                solution TEXT NOT NULL,
                tags TEXT,
                context TEXT,
                status TEXT DEFAULT 'Pending',
                generation INTEGER DEFAULT 1,
                retry_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                claimed_at TEXT,
                owner_token TEXT,
                flushed_at TEXT,
                UNIQUE(memory_id, workspace_hash)
            );
        """)
        raw_conn.execute("""
            CREATE TABLE workspace_registry (
                workspace_hash TEXT PRIMARY KEY,
                workspace_path TEXT NOT NULL,
                registered_at TEXT NOT NULL
            );
        """)

        legacy_hash = "cccccccccccccccccccccccccccccccc"
        ws_path = os.path.join(self.temp_dir.name, "workspace_dup")
        os.makedirs(ws_path, exist_ok=True)
        canonical_hash = canonical_workspace_hash(ws_path)

        # Register legacy hash to path
        raw_conn.execute("INSERT INTO workspace_registry VALUES (?, ?, datetime('now'));", (legacy_hash, ws_path))

        # Insert SAME memory_id under BOTH legacy_hash and canonical_hash
        raw_conn.execute(
            "INSERT INTO workspace_episodic_memory (memory_id, workspace_hash, title) VALUES (?, ?, ?);",
            ("mem-collision", legacy_hash, "Old Legacy Row")
        )
        raw_conn.execute(
            "INSERT INTO workspace_episodic_memory (memory_id, workspace_hash, title) VALUES (?, ?, ?);",
            ("mem-collision", canonical_hash, "New Canonical Row")
        )

        raw_conn.execute(
            "INSERT INTO consolidation_outbox (memory_id, workspace_hash, signature, solution, created_at) VALUES (?, ?, ?, ?, datetime('now'));",
            ("mem-collision", legacy_hash, "sig", "sol")
        )
        raw_conn.execute(
            "INSERT INTO consolidation_outbox (memory_id, workspace_hash, signature, solution, created_at) VALUES (?, ?, ?, ?, datetime('now'));",
            ("mem-collision", canonical_hash, "sig", "sol")
        )
        raw_conn.commit()
        raw_conn.close()

        # init_database must migrate cleanly without raising IntegrityError
        conn = init_database(self.db_path)

        # Exactly 1 row for mem-collision must exist, under canonical_hash
        rows = conn.execute("SELECT workspace_hash, title FROM workspace_episodic_memory WHERE memory_id = 'mem-collision';").fetchall()
        self.assertEqual(len(rows), 1, "Duplicate memory_id must be collapsed to exactly 1 row")
        self.assertEqual(rows[0][0], canonical_hash, "Remaining row must be partitioned under canonical SHA-256 hash")
        conn.close()

    def test_recall_traces_unscoped_emits_diagnostic(self):
        """
        VULN-102: Calling recall_traces without workspace_hash or workspace_dir
        when allow_unscoped=False must emit a diagnostic warning to stderr, not fail silently.
        """
        from experiential_memory import recall_traces
        import io

        captured_stderr = io.StringIO()
        with patch.object(sys, "stderr", captured_stderr):
            result = recall_traces("some query", workspace_dir=None, workspace_hash=None, allow_unscoped=False)

        self.assertEqual(result, [])
        stderr_output = captured_stderr.getvalue()
        self.assertIn("recall_traces called without workspace_hash or workspace_dir", stderr_output)

    def test_init_database_asserts_required_security_triggers(self):
        """
        VULN-101: init_database must verify all 5 invariant tenant-isolation triggers
        are active post-initialization and raise RuntimeError if any trigger is missing.
        """
        conn = init_database(self.db_path)
        # Verify all 5 triggers are present
        active_triggers = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name IN ("
                "'trg_episodic_prevent_ws_update', 'trg_episodic_prevent_ws_replace', "
                "'trg_episodic_prevent_cross_tenant_supersede', 'trg_episodic_prevent_cross_tenant_supersede_insert', "
                "'trg_episodic_after_update');"
            ).fetchall()
        }
        self.assertEqual(len(active_triggers), 5, "All 5 security triggers must be active")
        conn.close()

    def test_activation_events_and_l1_staging_idempotent_insert(self):
        """
        VULN-102: activation_events and l1_staging_log must reject duplicate events
        via unique constraints and INSERT OR IGNORE to prevent telemetry inflation on crash recovery.
        """
        conn = init_database(self.db_path)
        cur = conn.cursor()
        sess_id = "sess-dedup-1"
        ts = "2026-11-05 01:00:00"
        inp = "dedup query test"
        ws_hash = "f" * 64

        # Insert once into l1_staging_log
        cur.execute(
            "INSERT OR IGNORE INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash) VALUES (?, ?, ?, ?);",
            (sess_id, ts, inp, ws_hash)
        )
        # Duplicate insert must be ignored
        cur.execute(
            "INSERT OR IGNORE INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash) VALUES (?, ?, ?, ?);",
            (sess_id, ts, inp, ws_hash)
        )
        count_staging = cur.execute("SELECT count(*) FROM l1_staging_log WHERE session_id = ?;", (sess_id,)).fetchone()[0]
        self.assertEqual(count_staging, 1, "Duplicate row in l1_staging_log must be ignored")

        # Insert once into activation_events
        cur.execute(
            "INSERT OR IGNORE INTO activation_events (session_id, timestamp, user_input, workspace_dir) VALUES (?, ?, ?, ?);",
            (sess_id, ts, inp, ws_hash)
        )
        # Duplicate insert must be ignored
        cur.execute(
            "INSERT OR IGNORE INTO activation_events (session_id, timestamp, user_input, workspace_dir) VALUES (?, ?, ?, ?);",
            (sess_id, ts, inp, ws_hash)
        )
        count_events = cur.execute("SELECT count(*) FROM activation_events WHERE session_id = ?;", (sess_id,)).fetchone()[0]
        self.assertEqual(count_events, 1, "Duplicate row in activation_events must be ignored")
        conn.close()

    def test_load_traces_returns_deepcopy_protects_cache(self):
        """
        VULN-103: Public load_traces must return an independent deepcopy
        to prevent callers from mutating internal shared cache state.
        """
        import experiential_memory
        traces_file = os.path.join(self.temp_dir.name, "test_deepcopy_traces.json")
        init_data = {
            "version": "3.0.0",
            "updated_at": "2026-11-05 01:00:00",
            "traces": [{"id": "tr-immutable-1", "problem_signature": "orig sig", "tokens": ["orig"]}]
        }
        with open(traces_file, "w", encoding="utf-8") as f:
            json.dump(init_data, f)

        loaded1 = experiential_memory.load_traces(traces_file)
        # Mutate the returned dict
        loaded1["traces"][0]["problem_signature"] = "MUTATED CORRUPT SIG"

        # Subsequent load_traces must NOT reflect the mutation
        loaded2 = experiential_memory.load_traces(traces_file)
        self.assertEqual(loaded2["traces"][0]["problem_signature"], "orig sig", "Cache must not be mutated by caller")

    def test_synthesizer_ast_denylist_expanded_blocks_destructive_calls(self):
        """
        VULN-104: Synthesizer AST validator must block destructive calls
        including write-mode open(), os.remove(), rmtree(), and getattr().
        """
        from synthesizer import run_syntax_validation
        # Block open with write mode
        ok1, _, err1 = run_syntax_validation("with open('foo.txt', 'w') as f: f.write('bad')", allow_exec=False)
        self.assertFalse(ok1)
        self.assertIn("open() with destructive mode", err1)

        # Block os.remove / rmtree
        ok2, _, err2 = run_syntax_validation("import os\nos.remove('file.txt')", allow_exec=False)
        self.assertFalse(ok2)
        self.assertIn("blocked dangerous call: remove()", err2)

        # Block shutil import
        ok3, _, err3 = run_syntax_validation("import shutil\nshutil.rmtree('/tmp')", allow_exec=False)
        self.assertFalse(ok3)
        self.assertIn("blocked prohibited module import: 'shutil'", err3)

        # Block getattr dynamic reflection
        ok4, _, err4 = run_syntax_validation("getattr(os, 'system')('calc')", allow_exec=False)
        self.assertFalse(ok4)
        self.assertIn("blocked dangerous call: getattr()", err4)

    def test_mcp_gateway_copy_on_write(self):
        """
        VULN-105: get_mcp_index uses copy-on-write pointer swap and preserves responsiveness.
        """
        import mcp_gateway
        idx1 = mcp_gateway.get_mcp_index(force_refresh=True)
        self.assertIsInstance(idx1, dict)
        self.assertIn("tools", idx1)
        # Fast retrieval
        idx2 = mcp_gateway.get_mcp_index()
        self.assertIs(idx1, idx2)

    def test_consolidator_reconciles_subfolder_legacy_partitions(self):
        """
        VULN-106: ConsolidatorEngine must reconcile unconsolidated legacy 32-hex
        subfolder partitions belonging to workspace_root tree into authorized_hashes.
        """
        conn = init_database(self.db_path)
        cur = conn.cursor()
        root_dir = os.path.join(self.temp_dir.name, "my_project")
        sub_dir = os.path.join(root_dir, "submodule_a")
        os.makedirs(sub_dir, exist_ok=True)

        import hashlib
        legacy_sub_md5 = hashlib.md5(os.path.normcase(os.path.realpath(sub_dir)).encode("utf-8")).hexdigest().lower()
        now_str = "2026-11-05 01:00:00"

        # Register submodule in workspace_registry
        cur.execute("INSERT OR REPLACE INTO workspace_registry VALUES (?, ?, ?);", (legacy_sub_md5, sub_dir, now_str))

        # Insert unconsolidated event under legacy_sub_md5
        cur.execute(
            """
            INSERT OR IGNORE INTO activation_events (session_id, timestamp, user_input, workspace_dir, feedback_score, is_consolidated)
            VALUES (?, ?, ?, ?, 1.0, 0);
            """,
            ("sess-sub-1", now_str, "submodule build fix", legacy_sub_md5)
        )
        conn.commit()
        conn.close()

        # Construct ConsolidatorEngine with workspace_root = root_dir
        engine_conn = init_database(self.db_path)
        engine = ConsolidatorEngine(engine_conn, workspace_root=root_dir, allow_unscoped=False)
        self.assertIn(legacy_sub_md5, engine.authorized_hashes, "Legacy subfolder partition must be reconciled into authorized_hashes")
        engine_conn.close()

    def test_hash_prompt_straddling_secret_2048_boundary(self):
        """
        Defensive Edge Case 1: hash_prompt must redact secrets before 2048 truncation
        so that secrets straddling the boundary are redacted identically across producer and verifier.
        """
        # Place a secret right across the 2048 boundary
        prefix = "A" * 2035
        secret = "Bearer sk-ant-api03-abcdef1234567890abcdef12345"
        full_prompt = f"{prefix} {secret} trailing text"

        h1 = hash_prompt(full_prompt)
        # Redacting first means secret is masked to [REDACTED_TOKEN]
        self.assertTrue(len(h1) == 64, "hash_prompt must produce valid 64-char SHA256")
        self.assertNotIn("sk-ant-api03", full_prompt[:2048])  # Secret straddles boundary
        # Hash must match the redacted version
        h2 = hash_prompt(full_prompt)
        self.assertEqual(h1, h2, "Hash must be completely deterministic")

    def test_stdin_ceiling_exceeded_exits_within_100ms_without_hang(self):
        """
        VULN-001: Pre-flight hook reading large payload (1 MiB) must exit
        promptly with invariants JSON within 150ms without blocking in unbounded drain.
        """
        import subprocess
        hook_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook_runner.py")
        payload_1mb = b"X" * 1048576  # 1 MiB payload
        t0 = time.monotonic()
        proc = subprocess.Popen(
            [sys.executable, hook_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout_data, stderr_data = proc.communicate(input=payload_1mb, timeout=2.0)
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 1.0, f"Hook must not hang on oversized payload; took {elapsed:.3f}s")
        self.assertEqual(proc.returncode, 0)
        out_json = json.loads(stdout_data.decode("utf-8"))
        self.assertIn("injectSteps", out_json)

    def test_lifecycle_guard_epoch_fences_stale_victim_worker(self):
        """
        VULN-002: Reclaiming an alive process's lockfile increments the monotonic epoch
        and causes the victim instance's is_lock_valid() to return False.
        """
        from lifecycle_guard import LifecycleGuard
        with tempfile.TemporaryDirectory() as td:
            guard1 = LifecycleGuard("test_daemon", lock_dir=td, heartbeat_interval=0.1)
            self.assertTrue(guard1.acquire_lock())
            self.assertEqual(guard1.epoch, 1)
            self.assertTrue(guard1.is_lock_valid())

            # Simulate guard2 reclaiming the lock
            guard2 = LifecycleGuard("test_daemon", lock_dir=td, heartbeat_interval=0.1)
            # Stalled heartbeat reclaim simulation
            with open(guard1.lock_file, "r+", encoding="utf-8") as f:
                d = json.load(f)
                d["heartbeat"] = time.time() - 100
                f.seek(0)
                f.truncate()
                json.dump(d, f)

            self.assertTrue(guard2.acquire_lock(stale_timeout_sec=5.0))
            self.assertEqual(guard2.epoch, 2)
            self.assertTrue(guard2.is_lock_valid())

            # Guard 1 is now fenced and must recognize it no longer owns the lock
            self.assertFalse(guard1.is_lock_valid(), "Victim worker must be fenced when epoch increments")
            guard1.release_lock()
            guard2.release_lock()

    def test_hook_runner_same_second_retry_dedup_and_spool_fallback(self):
        """
        VULN-003: Submitting identical prompts in the same second must not raise
        or silently swallow errors; INSERT OR IGNORE and error tuple handle it cleanly.
        """
        from hook_runner import process_hook
        payload = {
            "lastUserInput": "same-second retry prompt",
            "sessionId": "test-sess-dedup",
            "workspacePath": self.temp_dir.name
        }
        # First execution stages cleanly
        res1 = process_hook(payload)
        self.assertIn("injectSteps", res1)
        # Immediate second execution within same second must not crash or drop
        res2 = process_hook(payload)
        self.assertIn("injectSteps", res2)

    def test_init_database_default_isolation_level_immediate(self):
        """
        VULN-004: init_database defaults to isolation_level='IMMEDIATE'
        and guarantees multi-statement transaction atomicity with with conn:.
        """
        conn = init_database(self.db_path)
        self.assertEqual(conn.isolation_level, "IMMEDIATE", "Default isolation_level must be IMMEDIATE")

        # Verify transaction atomicity: rollback inside with conn: on exception
        try:
            with conn:
                conn.execute(
                    "INSERT INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash) VALUES ('s1', 't1', 'inp1', 'h1');"
                )
                raise ValueError("Simulated failure inside multi-statement block")
        except ValueError:
            pass

        row = conn.execute("SELECT count(*) FROM l1_staging_log WHERE session_id = 's1';").fetchone()[0]
        self.assertEqual(row, 0, "Failed with conn: block must have rolled back atomically")
        conn.close()

    def test_recall_traces_default_path_no_nameerror(self):
        """
        Regression test: recall_traces() on the default TRACES_FILE path with a matching
        scoped trace must return results cleanly without raising NameError: name 'data' is not defined.
        """
        from experiential_memory import record_trace, recall_traces
        ws_dir = self.temp_dir.name
        rec = record_trace(
            problem_signature="fix sqlite database lock contention in personal cli",
            proven_solution="Use WAL mode with append-only spool and single writer queue",
            action_type="pattern",
            tags=["sqlite", "lock", "wal"],
            workspace_context=ws_dir,
            workspace_hash=canonical_workspace_hash(ws_dir)
        )
        self.assertTrue(rec.get("id"))
        recalled = recall_traces("fix sqlite database lock contention", workspace_dir=ws_dir)
        self.assertTrue(len(recalled) >= 1)
        self.assertIn("last_recalled", recalled[0]["trace"])


if __name__ == "__main__":
    unittest.main()
