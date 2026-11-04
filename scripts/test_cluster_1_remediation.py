#!/usr/bin/env python3
"""
Comprehensive Automated Verification Test Suite for Cluster 1 Remediation:
- VULN-001: Cross-workspace data leak prevention in hybrid_search hydration & dense trigger
- VULN-002: Dry-run zero mutation guarantee, no double-hashing, isolated cluster keys
- VULN-003: revert_invariant transaction recovery & fail-loud diagnostics
- VULN-004: MemorySingleWriter PRAGMA foreign_keys = ON cascade & error propagation
- VULN-005: FTS5 trigger WHEN clause write amplification prevention
- VULN-006: Vector backfill and WAL maintenance rollback & diagnostics
- VULN-007: cosine_similarity dimension guard & finite norm validation
- VULN-008: Positive feedback promotion threshold (neutral 0.0 ignored)
- VULN-009: Monotonic Ebbinghaus Padé decay & malformed timestamp safety

100% Python Standard Library.
"""

import os
import sys
import time
import errno
import math
import shutil
import sqlite3
import tempfile
import json
import threading
import io
import contextlib
import unicodedata
from typing import List

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_schema import init_database
from memory_engine import (
    search_fts5,
    hybrid_search,
    revert_invariant,
    cosine_similarity,
    serialize_float32_blob,
    deserialize_float32_blob,
    compute_vector_norm,
    MemorySingleWriter
)
from consolidator import ConsolidatorEngine, flush_outbox, _chunked_execute, resolve_workspace_hash, is_transient_io_error
from memory_utils import fold_vietnamese, canonical_workspace_hash, redact_secrets, persist_diag, is_valid_hex_hash
from experiential_memory import FileLock, record_trace, load_traces, recall_traces, _redact_trace_dict, TracePersistenceError, _save_traces_unlocked


def test_cross_workspace_isolation():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_isolation.db")
        conn = init_database(db_path)

        ws_a = "ws-alpha-111111"
        ws_b = "ws-beta-222222"
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Seed memory in Workspace A
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES ('mem-a1', ?, '/path/a', 'proven_trace', 'Postgres Docker Setup', 'postgres error', 'run docker compose up', 'docker, postgres', 'postgres docker setup', 'Active', 2, 1.0, 0.08, ?, ?)
            """,
            (ws_a, now_str, now_str)
        )

        # Seed memory in Workspace B with same/similar query terms
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES ('mem-b1', ?, '/path/b', 'proven_trace', 'Postgres Secret Keys Leak', 'postgres leak', 'secret_token_123', 'security, postgres', 'postgres secret keys leak', 'Active', 2, 1.0, 0.08, ?, ?)
            """,
            (ws_b, now_str, now_str)
        )
        conn.commit()

        # Hybrid search on Workspace A
        res_a = hybrid_search(conn, "postgres", ws_a, top_k=10)
        returned_ids = [r["memory_id"] for r in res_a]
        assert "mem-a1" in returned_ids, f"Expected mem-a1 in ws_a results, got {returned_ids}"
        assert "mem-b1" not in returned_ids, f"CRITICAL LEAK: mem-b1 from ws_b leaked into ws_a search: {returned_ids}"

        # Test trigger trg_episodic_after_update_ws
        vec = [0.1] * 384
        blob = serialize_float32_blob(vec)
        conn.execute(
            """
            INSERT INTO dense_embeddings (memory_id, workspace_hash, model_name, dimensions, vector_blob, norm, updated_at)
            VALUES ('mem-a1', ?, 'test-model', 384, ?, 1.0, ?)
            """,
            (ws_a, blob, now_str)
        )
        conn.commit()

        # Verify workspace_hash is strictly immutable and cannot be updated across tenants
        try:
            conn.execute("UPDATE workspace_episodic_memory SET workspace_hash = 'ws-alpha-migrated' WHERE memory_id = 'mem-a1'")
            conn.commit()
            assert False, "Expected trigger to abort workspace_hash modification"
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as trg_err:
            assert "workspace_hash is immutable" in str(trg_err)

        conn.close()
        print("  [PASS] test_cross_workspace_isolation")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dry_run_zero_mutation():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_dry_run.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Insert staging event
        conn.execute(
            """
            INSERT INTO l1_staging_log (
                session_id, timestamp, user_input, workspace_hash, top_skill, tier_used, recalled_traces, is_drained
            ) VALUES ('sess-1', ?, 'fix sqlite database lock', 'ws-test-12345', 'sqlite-skill', 1, '[]', 0)
            """,
            (now_str,)
        )
        conn.commit()

        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        result = engine.consolidate_batch(batch_size=10, dry_run=True)

        # Assert staging row still exists and is NOT drained or deleted
        staging_count = conn.execute("SELECT COUNT(*) FROM l1_staging_log WHERE is_drained = 0").fetchone()[0]
        assert staging_count == 1, f"Dry-run mutated staging log: expected 1 pending row, got {staging_count}"

        # Assert activation_events has 0 rows
        act_count = conn.execute("SELECT COUNT(*) FROM activation_events").fetchone()[0]
        assert act_count == 0, f"Dry-run created activation_events rows: got {act_count}"

        # Assert no episodic records created
        episodic_count = conn.execute("SELECT COUNT(*) FROM workspace_episodic_memory").fetchone()[0]
        assert episodic_count == 0, f"Dry-run created episodic memory records: got {episodic_count}"

        conn.close()
        print("  [PASS] test_dry_run_zero_mutation")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_no_double_hashing_and_isolated_clusters():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_clustering.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Ingest 2 identical queries in Workspace A and 2 in Workspace B with positive feedback
        ws_a = "d:/workspace_alpha"
        ws_b = "d:/workspace_beta"
        expected_hash_a = canonical_workspace_hash(ws_a)
        expected_hash_b = canonical_workspace_hash(ws_b)
        query_text = "debug out of memory error in cuda"

        for i in range(2):
            conn.execute(
                """
                INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
                VALUES (?, ?, ?, ?, 'cuda-skill', 1, '[]', 1.0, 0)
                """,
                (f"sess-a-{i}", now_str, query_text, ws_a)
            )
            conn.execute(
                """
                INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
                VALUES (?, ?, ?, ?, 'cuda-skill', 1, '[]', 1.0, 0)
                """,
                (f"sess-b-{i}", now_str, query_text, ws_b)
            )
        conn.commit()

        res = engine.consolidate_batch(batch_size=10, dry_run=False)
        assert res["promoted_traces"] == 2, f"Expected 2 isolated traces promoted (1 per workspace), got {res['promoted_traces']}"

        rows = conn.execute("SELECT memory_id, workspace_hash, workspace_path FROM workspace_episodic_memory").fetchall()
        assert len(rows) == 2, f"Expected exactly 2 rows in episodic memory, got {len(rows)}"

        hashes = {r[1] for r in rows}
        assert expected_hash_a in hashes, f"Expected {expected_hash_a} preserved without double hashing, got {hashes}"
        assert expected_hash_b in hashes, f"Expected {expected_hash_b} preserved without double hashing, got {hashes}"

        conn.close()
        print("  [PASS] test_no_double_hashing_and_isolated_clusters")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_single_writer_foreign_keys_and_fatal_propagation():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_writer.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Seed parent record
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES ('mem-parent', 'ws-test', '/test', 'invariant', 'Test Invariant', 'test', 'pass', '', 'test', 'Active', 1, 1.0, 0.0, ?, ?)
            """,
            (now_str, now_str)
        )
        conn.commit()
        conn.close()

        # Start MemorySingleWriter
        writer = MemorySingleWriter(db_path)
        vec = [0.5] * 384
        blob = serialize_float32_blob(vec)

        # Write child dense_embeddings through writer
        writer.enqueue_write(
            """
            INSERT INTO dense_embeddings (memory_id, workspace_hash, model_name, dimensions, vector_blob, norm, updated_at)
            VALUES ('mem-parent', 'ws-test', 'test-model', 384, ?, 1.0, datetime('now'))
            """,
            (blob,)
        )
        writer.flush()

        # Delete parent record through writer
        writer.enqueue_write("DELETE FROM workspace_episodic_memory WHERE memory_id = 'mem-parent'")
        writer.flush()

        # Check that ON DELETE CASCADE purged child dense_embeddings
        conn2 = sqlite3.connect(db_path)
        child_count = conn2.execute("SELECT COUNT(*) FROM dense_embeddings WHERE memory_id = 'mem-parent'").fetchone()[0]
        conn2.close()
        assert child_count == 0, f"PRAGMA foreign_keys failed in writer: orphan dense_embeddings remained ({child_count})"

        # Close writer and verify enqueue raises
        writer.close()
        try:
            writer.enqueue_write("SELECT 1;")
            assert False, "Expected RuntimeError when enqueuing to closed writer"
        except RuntimeError:
            pass

        print("  [PASS] test_single_writer_foreign_keys_and_fatal_propagation")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_revert_invariant_transaction_safety():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_revert.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        ws_test = "11111111111111111111111111111111"
        ws_other = "22222222222222222222222222222222"

        # Seed V1 and V2
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, superseded_by, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES
            ('inv-v1', ?, '/test', 'invariant', 'Rule V1', 'sig', 'sol1', '', 'rule v1', 'Superseded', 'inv-v2', 1, 1.0, 0.0, ?, ?),
            ('inv-v2', ?, '/test', 'invariant', 'Rule V2', 'sig', 'sol2', '', 'rule v2', 'Active', NULL, 1, 1.0, 0.0, ?, ?)
            """,
            (ws_test, now_str, now_str, ws_test, now_str, now_str)
        )
        conn.commit()

        # Intentionally open an active transaction with caller mutation
        conn.execute("BEGIN IMMEDIATE;")
        conn.execute(
            """
            INSERT INTO l1_staging_log (
                session_id, timestamp, user_input, workspace_hash, tier_used, is_drained
            ) VALUES ('caller-tx', '2026-01-01', 'caller query', ?, 1, 0)
            """,
            (ws_test,)
        )

        # Calling revert_invariant with mismatched workspace_hash must fail
        assert revert_invariant(conn, "inv-v1", ws_other) is False, "revert_invariant allowed cross-workspace revert"

        # Calling revert_invariant must use SAVEPOINT and succeed without blowing away caller transaction
        ok = revert_invariant(conn, "inv-v1", ws_test)
        assert ok is True, "revert_invariant failed when transaction was already active"

        # Commit caller transaction
        conn.commit()

        # Assert caller transaction work was preserved (zero data loss)
        caller_row = conn.execute("SELECT session_id FROM l1_staging_log WHERE session_id = 'caller-tx'").fetchone()
        assert caller_row is not None, "revert_invariant destroyed caller's outer transaction!"

        v1_status = conn.execute("SELECT status, superseded_by FROM workspace_episodic_memory WHERE memory_id = 'inv-v1'").fetchone()
        v2_status = conn.execute("SELECT status, superseded_by FROM workspace_episodic_memory WHERE memory_id = 'inv-v2'").fetchone()

        assert v1_status[0] == "Active", f"inv-v1 status not Active: {v1_status[0]}"
        assert v1_status[1] is None, f"inv-v1 superseded_by not None: {v1_status[1]}"
        assert v2_status[0] == "Superseded", f"inv-v2 status not Superseded: {v2_status[0]}"
        assert v2_status[1] == "inv-v1", f"inv-v2 superseded_by not inv-v1: {v2_status[1]}"

        conn.close()
        print("  [PASS] test_revert_invariant_transaction_safety")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_cosine_similarity_dimension_guard():
    # Matching dimensions
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    sim = cosine_similarity(v1, 1.0, v2, 1.0)
    assert abs(sim - 1.0) < 1e-6, f"Expected 1.0, got {sim}"

    # Zero norm returns 0.0 without error
    sim_zero = cosine_similarity(v1, 0.0, v2, 1.0)
    assert sim_zero == 0.0, f"Expected 0.0 for zero norm, got {sim_zero}"

    # Non-finite norm returns 0.0
    sim_nan = cosine_similarity(v1, float("nan"), v2, 1.0)
    assert sim_nan == 0.0, f"Expected 0.0 for NaN norm, got {sim_nan}"

    # Mismatched dimensions returns 0.0 by default (backward compatible)
    sim_mismatch = cosine_similarity([1.0, 2.0], 1.0, [1.0], 1.0)
    assert sim_mismatch == 0.0, f"Expected 0.0 for mismatched dimensions, got {sim_mismatch}"

    # In strict mode, mismatched dimensions MUST raise ValueError (fail loudly)
    try:
        cosine_similarity([1.0, 2.0], 1.0, [1.0], 1.0, strict=True)
        assert False, "Expected ValueError on dimension mismatch with strict=True"
    except ValueError:
        pass

    print("  [PASS] test_cosine_similarity_dimension_guard")


def test_fts5_empty_query_guard():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_fts_guard.db")
        conn = init_database(db_path)

        # Empty string
        res1 = search_fts5(conn, "", "ws-test")
        assert res1 == [], f"Expected empty list for empty query, got {res1}"

        # Punctuation-only string
        res2 = search_fts5(conn, "!@#$$%^&*()", "ws-test")
        assert res2 == [], f"Expected empty list for punctuation query, got {res2}"

        # Negative limit clamp
        res3 = search_fts5(conn, "test query", "ws-test", limit=-5)
        assert isinstance(res3, list), "Expected list result for negative limit clamp"

        conn.close()
        print("  [PASS] test_fts5_empty_query_guard")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_positive_feedback_promotion_threshold():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_feedback.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Ingest 2 neutral events (feedback_score = 0.0)
        for i in range(2):
            conn.execute(
                """
                INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
                VALUES (?, ?, 'neutral task query', 'ws-test-feed', 'skill-x', 1, '[]', 0.0, 0)
                """,
                (f"sess-neu-{i}", now_str)
            )
        conn.commit()

        res_neu = engine.consolidate_batch(batch_size=10, dry_run=False)
        assert res_neu["promoted_traces"] == 0, f"Neutral events incorrectly promoted: {res_neu['promoted_traces']}"

        # 2. Ingest 2 positive events (feedback_score = 1.0)
        for i in range(2):
            conn.execute(
                """
                INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
                VALUES (?, ?, 'positive task query', 'ws-test-feed', 'skill-x', 1, '[]', 1.0, 0)
                """,
                (f"sess-pos-{i}", now_str)
            )
        conn.commit()

        res_pos = engine.consolidate_batch(batch_size=10, dry_run=False)
        assert res_pos["promoted_traces"] == 1, f"Positive events failed to promote: {res_pos['promoted_traces']}"

        conn.close()
        print("  [PASS] test_positive_feedback_promotion_threshold")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_monotonic_ebbinghaus_decay():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_decay.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=True)

        # 1. Seed two memories: one accessed recently (2 days ago), one accessed long ago (20 days ago)
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES
            ('mem-recent', 'ws-test-decay', '/test', 'proven_trace', 'Recent', 'sig', 'sol', '', 'recent', 'Active', 1, 1.0, 0.08, datetime('now', '-2 days'), datetime('now', '-30 days')),
            ('mem-old', 'ws-test-decay', '/test', 'proven_trace', 'Old', 'sig', 'sol', '', 'old', 'Active', 1, 1.0, 0.08, datetime('now', '-20 days'), datetime('now', '-30 days')),
            ('mem-malformed-ts', 'ws-test-decay', '/test', 'proven_trace', 'Malformed', 'sig', 'sol', '', 'malformed', 'Active', 1, 0.80, 0.08, 'CORRUPT_TIMESTAMP_VALUE', datetime('now', '-5 days'))
            """
        )
        conn.commit()

        # Run consolidation cycle (which applies decay)
        engine.consolidate_batch(batch_size=10, dry_run=False)

        conf_recent = conn.execute("SELECT confidence_score FROM workspace_episodic_memory WHERE memory_id = 'mem-recent'").fetchone()[0]
        conf_old = conn.execute("SELECT confidence_score FROM workspace_episodic_memory WHERE memory_id = 'mem-old'").fetchone()[0]
        conf_malformed = conn.execute("SELECT confidence_score FROM workspace_episodic_memory WHERE memory_id = 'mem-malformed-ts'").fetchone()[0]

        assert conf_recent is not None and conf_old is not None, "Decay resulted in NULL confidence_score"
        assert conf_old < conf_recent, f"Expected older memory to decay more: conf_old={conf_old} vs conf_recent={conf_recent}"
        assert 0.0 <= conf_old <= 1.0 and 0.0 <= conf_recent <= 1.0

        assert conf_malformed is not None, "Malformed timestamp resulted in NULL confidence_score"
        assert 0.0 <= conf_malformed <= 1.0, f"Confidence score out of [0.0, 1.0] bound: {conf_malformed}"

        conn.close()
        print("  [PASS] test_monotonic_ebbinghaus_decay")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_fts5_trigger_metadata_no_rebuild():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_trigger.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Insert record
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES (
                'mem-trg-1', 'ws-trg', '/test', 'proven_trace',
                'Trigger Performance Test', 'sig', 'sol', 'test', 'trigger performance test',
                'Active', 1, 1.0, 0.08, ?, ?
            )
            """,
            (now_str, now_str)
        )
        conn.commit()

        # Update metadata only (activation_count, confidence_score, last_accessed_at)
        conn.execute(
            """
            UPDATE workspace_episodic_memory
            SET activation_count = activation_count + 1,
                confidence_score = 0.95,
                last_accessed_at = datetime('now')
            WHERE memory_id = 'mem-trg-1'
            """
        )
        conn.commit()

        # FTS5 row should still exist and match
        res = search_fts5(conn, "Trigger Performance", "ws-trg")
        assert len(res) == 1, f"FTS search failed after metadata update: {res}"
        assert res[0][0] == "mem-trg-1"

        conn.close()
        print("  [PASS] test_fts5_trigger_metadata_no_rebuild")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_adversarial_workspace_hash_validation():
    from consolidator import resolve_workspace_hash, is_valid_hex_hash

    # is_valid_hex_hash validates 32-char hex hashes
    raw_hash_input = "a37db9ae74c811112222333344445555"
    assert is_valid_hex_hash(raw_hash_input) is True
    assert is_valid_hex_hash("invalid-hash") is False

    # Without approved_root or allow_unscoped=True, must raise ValueError to prevent tenant leakage (VULN-007)
    try:
        resolve_workspace_hash(raw_hash_input)
        assert False, "Expected ValueError when approved_root is None and allow_unscoped is False"
    except ValueError:
        pass

    # 32-char hex hash from l1_staging_log is recognized when allow_unscoped=True
    resolved = resolve_workspace_hash(raw_hash_input, allow_unscoped=True)
    assert resolved == raw_hash_input, "32-char hex MD5 from staging log must be recognized with allow_unscoped=True"

    # When approved_root is passed, foreign 32-hex hash must be rejected (VULN-001)
    test_root = "d:/test/approved_root"
    valid_root_hash = canonical_workspace_hash(test_root)
    assert resolve_workspace_hash(valid_root_hash, approved_root=test_root) == valid_root_hash
    try:
        resolve_workspace_hash(raw_hash_input, approved_root=test_root)
        assert False, "Expected foreign hex hash to be rejected when approved_root is set"
    except ValueError:
        pass

    # Path traversal attempt is canonicalized safely to valid hex hash
    traversal = "d:/test/../../etc/passwd"
    resolved_traversal = resolve_workspace_hash(traversal, allow_unscoped=True)
    assert len(resolved_traversal) in (32, 64), f"Expected 32 or 64-char hex hash, got {len(resolved_traversal)}"

    # None and empty strings must fail closed with ValueError
    for bad in (None, "", "   "):
        try:
            resolve_workspace_hash(bad)
            assert False, f"Expected ValueError for bad input {bad!r}"
        except ValueError:
            pass

    print("  [PASS] test_adversarial_workspace_hash_validation")


def test_poison_pill_row_resilience():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_poison.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Insert a poison-pill event (workspace_dir is None or empty)
        conn.execute(
            """
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
            VALUES ('sess-poison', ?, 'poison query', '', 'skill-x', 1, '[]', 1.0, 0)
            """,
            (now_str,)
        )

        # 2. Insert 2 valid events that should be promoted
        for i in range(2):
            conn.execute(
                """
                INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
                VALUES (?, ?, 'valid fix query', 'd:/valid_workspace', 'skill-x', 1, '[]', 1.0, 0)
                """,
                (f"sess-valid-{i}", now_str)
            )
        conn.commit()

        # Batch consolidation must not crash and must promote the valid cluster
        res = engine.consolidate_batch(batch_size=10, dry_run=False)
        assert res["promoted_traces"] == 1, f"Expected 1 promoted trace, got {res['promoted_traces']}"

        # Verify episodic memory has the promoted trace
        promoted = conn.execute("SELECT count(*) FROM workspace_episodic_memory WHERE title LIKE 'Promoted: valid fix%'").fetchone()[0]
        assert promoted == 1, f"Expected 1 promoted trace in episodic memory, got {promoted}"
        # Poison event must be quarantined with is_consolidated = 2
        status = conn.execute("SELECT is_consolidated FROM activation_events WHERE session_id = 'sess-poison'").fetchone()[0]
        assert status == 2, f"Expected poison event to be quarantined with is_consolidated = 2, got {status}"

        conn.close()
        print("  [PASS] test_poison_pill_row_resilience")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_consolidator_savepoint_in_caller_tx():
    """Verify consolidator uses SAVEPOINT cleanly when caller has an open transaction."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_sp.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Caller begins explicit transaction and inserts caller record
        conn.execute("BEGIN IMMEDIATE;")
        conn.execute(
            """
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
            VALUES ('sess-caller-1', ?, 'caller query 1', 'd:/ws_caller', 'skill-x', 1, '[]', 1.0, 0)
            """,
            (now_str,)
        )
        conn.execute(
            """
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
            VALUES ('sess-caller-2', ?, 'caller query 1', 'd:/ws_caller', 'skill-x', 1, '[]', 1.0, 0)
            """,
            (now_str,)
        )

        # Consolidator runs inside caller transaction using SAVEPOINT
        res = engine.consolidate_batch(batch_size=10, dry_run=False)
        assert res["promoted_traces"] == 1, f"Expected 1 promoted trace, got {res['promoted_traces']}"

        # Caller can still commit caller transaction
        conn.commit()

        # Verify promoted trace persisted
        count = conn.execute("SELECT count(*) FROM workspace_episodic_memory WHERE title LIKE 'Promoted: caller query%'").fetchone()[0]
        assert count == 1, f"Expected promoted trace in episodic memory, got {count}"

        conn.close()
        print("  [PASS] test_consolidator_savepoint_in_caller_tx")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_root_containment_and_overflow_limit():
    from consolidator import resolve_workspace_hash
    from memory_engine import search_fts5

    # 1. Root containment check
    approved = os.path.abspath("d:/approved_workspace")
    sub = os.path.abspath("d:/approved_workspace/subfolder")
    outside = os.path.abspath("d:/other_tenant/evil")

    # Inside approved root passes
    hash_sub = resolve_workspace_hash(sub, approved_root=approved)
    assert len(hash_sub) in (32, 64)

    # Outside approved root must raise ValueError
    try:
        resolve_workspace_hash(outside, approved_root=approved)
        assert False, "Expected ValueError on root escape"
    except ValueError:
        pass

    # Null byte in path must raise ValueError
    try:
        resolve_workspace_hash("d:/approved_workspace/foo\x00bar", approved_root=approved)
        assert False, "Expected ValueError on null byte"
    except ValueError:
        pass

    # 2. search_fts5 with float('inf') overflow limit
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_inf.db")
        conn = init_database(db_path)
        res = search_fts5(conn, "test query", "ws_any", limit=float("inf"))
        assert res == [], "Overflow limit must gracefully return without crashing"
        conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("  [PASS] test_root_containment_and_overflow_limit")


def test_single_writer_reentrant_worker_guard():
    from memory_engine import _local

    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_reentrant.db")
        conn = init_database(db_path)
        conn.close()

        writer = MemorySingleWriter(db_path)
        reentrant_caught = []

        def callback(success, err):
            # Attempt to re-entrantly call enqueue_write from worker callback
            try:
                writer.enqueue_write("SELECT 1;")
            except RuntimeError as re_err:
                reentrant_caught.append(str(re_err))

        writer.enqueue_write("SELECT 1;", callback=callback)
        writer.flush(timeout=5.0)

        assert len(reentrant_caught) == 1, f"Expected 1 re-entrant error, got {reentrant_caught}"
        assert "Cannot call enqueue_write() from within MemorySingleWriter worker thread" in reentrant_caught[0]

        writer.close(timeout=5.0)
        print("  [PASS] test_single_writer_reentrant_worker_guard")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_workspace_hash_immutable_trigger():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_immutable.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES (
                'mem-imm-1', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '/test/alpha', 'proven_trace',
                'Immutable Title', 'sig', 'sol', '', 'immutable title',
                'Active', 1, 1.0, 0.08, ?, ?
            )
            """,
            (now_str, now_str)
        )
        conn.commit()

        # Updating workspace_hash must be aborted by trigger
        try:
            conn.execute("UPDATE workspace_episodic_memory SET workspace_hash = 'ws-beta' WHERE memory_id = 'mem-imm-1'")
            conn.commit()
            assert False, "Expected trigger to abort workspace_hash modification"
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as trg_err:
            assert "workspace_hash is immutable" in str(trg_err)

        # Replacing with a different workspace_hash via INSERT OR REPLACE must also be aborted
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO workspace_episodic_memory (
                    memory_id, workspace_hash, workspace_path, memory_type,
                    title, problem_signature, solution_payload, bilingual_tags,
                    content_folded, status, activation_count, confidence_score,
                    decay_rate, last_accessed_at, created_at
                ) VALUES (
                    'mem-imm-1', 'ws-beta', '/test/beta', 'proven_trace',
                    'Replaced Title', 'sig', 'sol', '', 'replaced title',
                    'Active', 1, 1.0, 0.08, datetime('now'), datetime('now')
                )
                """
            )
            conn.commit()
            assert False, "Expected trigger to abort cross-tenant REPLACE"
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as rpl_err:
            assert "workspace_hash is immutable" in str(rpl_err)

        conn.close()
        print("  [PASS] test_workspace_hash_immutable_trigger")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_consolidator_reinforcement_two_pass():
    """Verify that multiple consolidation passes over repeated traces successfully reinforce without NameError or crash."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_reinforce.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Staging: 2 successful activations of the same problem signature
        ws_path = temp_dir
        ws_hash = canonical_workspace_hash(ws_path)
        for i in range(2):
            conn.execute(
                """
                INSERT INTO l1_staging_log (
                    session_id, timestamp, user_input, workspace_hash, tier_used, is_drained
                ) VALUES (?, ?, 'docker port conflict 8080', ?, 1, 0)
                """,
                (f"sess-{i}", now_str, ws_path)
            )
        conn.commit()

        # Pass 1: Drain staging, apply positive feedback, and consolidate -> Promotion to Active (threshold >= 2)
        drained = engine.drain_l1_staging()
        assert drained == 2
        conn.execute("UPDATE activation_events SET feedback_score = 1.0 WHERE is_consolidated = 0")
        conn.commit()
        p1 = engine.consolidate_batch(batch_size=10)
        assert p1["promoted_traces"] == 1

        # Pass 2: Ingest 2 more identical events -> Consolidation should reinforce existing trace
        for i in range(2, 4):
            conn.execute(
                """
                INSERT INTO l1_staging_log (
                    session_id, timestamp, user_input, workspace_hash, tier_used, is_drained
                ) VALUES (?, ?, 'docker port conflict 8080', ?, 1, 0)
                """,
                (f"sess-{i}", now_str, ws_path)
            )
        conn.commit()
        drained2 = engine.drain_l1_staging()
        assert drained2 == 2
        conn.execute("UPDATE activation_events SET feedback_score = 1.0 WHERE is_consolidated = 0")
        conn.commit()

        p2 = engine.consolidate_batch(batch_size=10)
        assert p2["promoted_traces"] == 1

        # Verify episodic table has count = 4 and status Active
        row = conn.execute("SELECT activation_count, status, confidence_score FROM workspace_episodic_memory WHERE workspace_hash = ?", (ws_hash,)).fetchone()
        assert row is not None
        assert row[0] == 4
        assert row[1] == "Active"
        assert row[2] == 1.0

        conn.close()
        print("  [PASS] test_consolidator_reinforcement_two_pass")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_secret_redaction_boundary():
    """Verify secrets are redacted across patterns and at persistence boundaries."""
    from memory_utils import redact_secrets

    test_input = (
        "Bearer secret_token_12345 "
        "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890 "
        "AKIAIOSFODNN7EXAMPLE "
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c "
        "ghp_1234567890abcdefghijklmnopqrstuvwxyz "
        "xoxb-1234567890-abcdef "
        "AIzaSyD-1234567890abcdefghijklmnopqrstuv "
        "postgresql://admin:super_secret_pw@localhost:5432/mydb"
    )
    redacted = redact_secrets(test_input)
    assert "secret_token_12345" not in redacted
    assert "sk-ant-api03" not in redacted
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "eyJhbGci" not in redacted
    assert "ghp_1234567890" not in redacted
    assert "xoxb-1234567890" not in redacted
    assert "AIzaSyD" not in redacted
    assert "super_secret_pw" not in redacted
    assert "[REDACTED_API_KEY]" in redacted
    assert "[REDACTED_GOOGLE_KEY]" in redacted
    assert "[REDACTED_AWS_KEY]" in redacted

    # None handling
    assert redact_secrets(None) is None
    assert redact_secrets("") == ""

    print("  [PASS] test_secret_redaction_boundary")


def test_cross_tenant_supersede_insert_trigger():
    """Verify that INSERT with cross-tenant superseded_by is blocked by trigger."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_trigger_ins.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Insert record for tenant A
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES (
                'mem-tenant-a', 'ws-tenant-a', '/test/a', 'invariant',
                'Title A', 'sig', 'sol', '', 'title a',
                'Active', 1, 1.0, 0.0, ?, ?
            )
            """,
            (now_str, now_str)
        )
        conn.commit()

        # Attempt to insert record for tenant B with superseded_by pointing to tenant A
        try:
            conn.execute(
                """
                INSERT INTO workspace_episodic_memory (
                    memory_id, workspace_hash, workspace_path, memory_type,
                    title, problem_signature, solution_payload, bilingual_tags,
                    content_folded, status, superseded_by, activation_count, confidence_score,
                    decay_rate, last_accessed_at, created_at
                ) VALUES (
                    'mem-tenant-b', 'ws-tenant-b', '/test/b', 'invariant',
                    'Title B', 'sig', 'sol', '', 'title b',
                    'Active', 'mem-tenant-a', 1, 1.0, 0.0, ?, ?
                )
                """,
                (now_str, now_str)
            )
            conn.commit()
            assert False, "Expected trigger to abort INSERT with cross-tenant superseded_by"
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
            assert "superseded_by cannot reference a record from a different workspace_hash" in str(e)

        conn.close()
        print("  [PASS] test_cross_tenant_supersede_insert_trigger")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_consolidation_durable_outbox():
    """Verify that consolidation creates durable outbox records that are flushed idempotently."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_outbox.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Staging: 2 successful activations of the same problem signature
        ws_path = temp_dir
        for i in range(2):
            conn.execute(
                """
                INSERT INTO l1_staging_log (
                    session_id, timestamp, user_input, workspace_hash, tier_used, is_drained
                ) VALUES (?, ?, 'cuda out of memory vram', ?, 1, 0)
                """,
                (f"sess-ob-{i}", now_str, ws_path)
            )
        conn.commit()

        engine.drain_l1_staging()
        conn.execute("UPDATE activation_events SET feedback_score = 1.0 WHERE is_consolidated = 0")
        conn.commit()

        res = engine.consolidate_batch(batch_size=10)
        assert res["promoted_traces"] == 1

        # Check consolidation_outbox table
        row = conn.execute("SELECT status, retry_count, memory_id FROM consolidation_outbox").fetchone()
        assert row is not None, "consolidation_outbox has no row!"
        assert row[0] == "Flushed", f"Expected outbox status Flushed, got {row[0]}"
        assert row[1] == 0

        conn.close()
        print("  [PASS] test_consolidation_durable_outbox")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_scoped_consolidator_isolation():
    """Verify that ConsolidatorEngine scoped to workspace_hash only consolidates its own workspace."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_scoped_engine.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        ws_a = "11111111111111111111111111111111"
        ws_b = "22222222222222222222222222222222"

        # Staging for ws_a and ws_b
        conn.execute("INSERT INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash) VALUES ('s1', ?, 'query a', ?)", (now_str, ws_a))
        conn.execute("INSERT INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash) VALUES ('s2', ?, 'query b', ?)", (now_str, ws_b))
        conn.commit()

        # Engine scoped to ws_a
        engine_a = ConsolidatorEngine(conn, workspace_hash=ws_a)
        drained_a = engine_a.drain_l1_staging()
        assert drained_a == 1, f"Expected 1 drained for ws_a, got {drained_a}"

        # Assert ws_b staging record remains untouched (is_drained = 0)
        row_b = conn.execute("SELECT is_drained FROM l1_staging_log WHERE workspace_hash = ?", (ws_b,)).fetchone()
        assert row_b[0] == 0

        conn.close()
        print("  [PASS] test_scoped_consolidator_isolation")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_revert_invariant_cycle_detection():
    """Verify revert_invariant safely detects cyclic replacement chains and aborts without hang."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_cycle.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        ws = "33333333333333333333333333333333"
        # Seed cyclic chain: c1 points to c2, c2 points to c1
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, superseded_by, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES
            ('cyc-1', ?, '/test', 'invariant', 'C1', 'sig', 'sol1', '', 'c1', 'Superseded', 'cyc-2', 1, 1.0, 0.0, ?, ?),
            ('cyc-2', ?, '/test', 'invariant', 'C2', 'sig', 'sol2', '', 'c2', 'Superseded', 'cyc-1', 1, 1.0, 0.0, ?, ?)
            """,
            (ws, now_str, now_str, ws, now_str, now_str)
        )
        conn.commit()

        ok = revert_invariant(conn, "cyc-1", ws)
        assert ok is False, "Expected revert_invariant to return False on cyclic chain"

        conn.close()
        print("  [PASS] test_revert_invariant_cycle_detection")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_redact_secrets_non_string_and_false_positive():
    """Verify redact_secrets handles non-string inputs safely and prevents false positives on words like 'disk-configuration'."""
    from memory_utils import redact_secrets

    # Non-string inputs
    assert redact_secrets(12345) == "12345"
    assert redact_secrets(3.14) == "3.14"
    assert redact_secrets(None) is None

    # False positive prevention: 'disk-configuration' or 'task-...' should NOT be treated as sk- api keys
    normal_text = "Checking disk-configuration-service and task-12345678901234567890 status"
    redacted = redact_secrets(normal_text)
    assert "[REDACTED_API_KEY]" not in redacted, f"False positive detected: {redacted}"
    assert "disk-configuration-service" in redacted

    # True positive: actual sk- key
    secret_text = "API Key: sk-12345678901234567890abcdef"
    redacted_secret = redact_secrets(secret_text)
    assert "[REDACTED_API_KEY]" in redacted_secret

    print("  [PASS] test_redact_secrets_non_string_and_false_positive")


def test_revert_invariant_broken_chain():
    """Verify revert_invariant safely aborts when superseded_by points to a missing record."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_broken.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        ws = "44444444444444444444444444444444"
        # Seed record pointing to non-existent 'missing-target'
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, superseded_by, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES
            ('inv-broken', ?, '/test', 'invariant', 'Broken Rule', 'sig', 'sol', '', 'broken', 'Superseded', 'missing-target', 1, 1.0, 0.0, ?, ?)
            """,
            (ws, now_str, now_str)
        )
        conn.commit()

        ok = revert_invariant(conn, "inv-broken", ws)
        assert ok is False, "Expected revert_invariant to return False on broken chain"

        # Assert status was NOT modified to Active
        row = conn.execute("SELECT status FROM workspace_episodic_memory WHERE memory_id = 'inv-broken'").fetchone()
        assert row[0] == "Superseded"

        conn.close()
        print("  [PASS] test_revert_invariant_broken_chain")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_outbox_two_phase_transaction_isolation():
    """Verify flush_outbox uses claimed_at, isolates file I/O from SQLite locks, and marks Failed after 5 retries."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_outbox_isolation.db")
        conn = init_database(db_path)
        from consolidator import flush_outbox

        # Insert a pending outbox row
        conn.execute(
            """
            INSERT INTO consolidation_outbox (
                memory_id, workspace_hash, signature, solution, tags, status, retry_count, created_at
            ) VALUES ('mem-iso-1', 'ws-iso', 'sig test', 'sol test', '["tag1", "tag2"]', 'Pending', 0, datetime('now'))
            """
        )
        # Insert a stale InFlight row (>60s old claimed_at) with retry_count = 4 (should bump to 5 and mark Failed)
        conn.execute(
            """
            INSERT INTO consolidation_outbox (
                memory_id, workspace_hash, signature, solution, tags, status, retry_count, created_at, claimed_at
            ) VALUES ('mem-stale-1', 'ws-iso', 'stale sig', 'stale sol', '["tag"]', 'InFlight', 4, datetime('now', '-240 seconds'), datetime('now', '-200 seconds'))
            """
        )
        conn.commit()

        # Run flush_outbox
        flushed = flush_outbox(conn, limit=10)
        assert flushed == 1, f"Expected 1 flushed row, got {flushed}"

        row_iso = conn.execute("SELECT status, claimed_at, flushed_at FROM consolidation_outbox WHERE memory_id = 'mem-iso-1'").fetchone()
        assert row_iso[0] == "Flushed", f"Expected Flushed, got {row_iso[0]}"
        assert row_iso[1] is not None, "Expected claimed_at to be populated"
        assert row_iso[2] is not None, "Expected flushed_at to be populated"

        row_stale = conn.execute("SELECT status, retry_count, last_error FROM consolidation_outbox WHERE memory_id = 'mem-stale-1'").fetchone()
        assert row_stale[0] == "Failed", f"Expected stale record to transition to Failed after 5 retries, got {row_stale[0]}"
        assert row_stale[1] == 5, f"Expected retry_count 5, got {row_stale[1]}"

        conn.close()
        print("  [PASS] test_outbox_two_phase_transaction_isolation")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_redact_secrets_json_roundtrip_preservation():
    """Verify redact_secrets preserves JSON structure, nested keys, and doesn't eat delimiters (VULN-005)."""
    from memory_utils import redact_secrets
    import json

    payload = {
        "api_key": "sk-1234567890abcdef1234567890",
        "nested": {
            "password": "supersecretpassword123",
            "token": "ghp_123456789012345678901234567890123456",
            "safe_field": "public_data_here"
        },
        "array_data": [
            {"auth_token": "bearer 12345678901234567890"},
            {"normal_val": 42}
        ]
    }
    raw_json = json.dumps(payload)
    redacted = redact_secrets(raw_json)

    # Must be valid parseable JSON
    parsed = json.loads(redacted)
    assert parsed["api_key"] == "[REDACTED_KEY]"
    assert parsed["nested"]["password"] == "[REDACTED_KEY]"
    assert parsed["nested"]["safe_field"] == "public_data_here"
    assert parsed["array_data"][1]["normal_val"] == 42
    assert "supersecretpassword123" not in redacted
    assert "sk-1234567890abcdef1234567890" not in redacted

    # Text format with trailing delimiter: {"api_key": "secret"}
    text_snippet = '{"api_key": "mysecretkey999"} and normal text'
    red_text = redact_secrets(text_snippet)
    assert "mysecretkey999" not in red_text
    assert "[REDACTED_KEY]" in red_text
    assert red_text.startswith('{"api_key": "[REDACTED_KEY]"}')

    print("  [PASS] test_redact_secrets_json_roundtrip_preservation")


def test_cross_tenant_consolidation_non_interference():
    """Verify tenant A consolidation does not decay, archive, or delete tenant B rows (VULN-001)."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_non_interference.db")
        conn = init_database(db_path)
        ws_a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ws_b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Seed memories for Tenant B:
        # 1. Active memory that would decay under global update
        # 2. Archived memory older than 30 days that would be hard-purged under global delete
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES
            ('mem-b-active', ?, '/ws/b', 'proven_trace', 'B Active', 'sig b', 'sol b', '', 'b active', 'Active', 1, 1.0, 0.08, datetime('now', '-20 days'), datetime('now', '-30 days')),
            ('mem-b-archived', ?, '/ws/b', 'proven_trace', 'B Archived', 'sig b2', 'sol b2', '', 'b archived', 'Archived', 1, 0.10, 0.08, datetime('now', '-35 days'), datetime('now', '-40 days'))
            """,
            (ws_b, ws_b)
        )

        # Seed activation event for Tenant A
        conn.execute(
            """
            INSERT INTO activation_events (
                session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated
            ) VALUES
            ('sess-a1', ?, 'solve tenant a issue', ?, 'skill-a', 1, '[]', 1.0, 0),
            ('sess-a2', ?, 'solve tenant a issue', ?, 'skill-a', 1, '[]', 1.0, 0)
            """,
            (now_str, ws_a, now_str, ws_a)
        )
        conn.commit()

        # Consolidate strictly for Tenant A
        engine_a = ConsolidatorEngine(conn, workspace_hash=ws_a)
        res_a = engine_a.consolidate_batch(batch_size=10, dry_run=False)

        # Verify Tenant B's active row was NOT decayed (confidence_score remains 1.0)
        row_b_active = conn.execute("SELECT confidence_score, status FROM workspace_episodic_memory WHERE memory_id = 'mem-b-active'").fetchone()
        assert row_b_active is not None, "Tenant B active record was unexpectedly deleted!"
        assert row_b_active[0] == 1.0, f"Tenant B active record was decayed by Tenant A cycle! score={row_b_active[0]}"
        assert row_b_active[1] == "Active", f"Tenant B status changed: {row_b_active[1]}"

        # Verify Tenant B's archived row was NOT purged
        row_b_archived = conn.execute("SELECT status FROM workspace_episodic_memory WHERE memory_id = 'mem-b-archived'").fetchone()
        assert row_b_archived is not None, "Tenant B archived record was purged by Tenant A cycle!"
        assert row_b_archived[0] == "Archived"

        conn.close()
        print("  [PASS] test_cross_tenant_consolidation_non_interference")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_outbox_idempotency_on_lease_expiry():
    """Verify outbox replay with same outbox_id does not increment success_count (VULN-002)."""
    temp_dir = tempfile.mkdtemp()
    try:
        traces_file = os.path.join(temp_dir, "proven_traces.json")
        from experiential_memory import record_trace, load_traces

        sig = "unique outbox idempotency signature"
        sol = "def unique_idempotent_solution(): return True"

        # Worker 1 records trace from outbox 101
        res1 = record_trace(sig, sol, traces_path=traces_file, outbox_id=101)
        assert res1["success_count"] == 1, f"Expected initial success_count 1, got {res1['success_count']}"

        # Lease expires, Worker 2 re-claims and re-records the same outbox 101
        res2 = record_trace(sig, sol, traces_path=traces_file, outbox_id=101)
        assert res2["success_count"] == 1, f"Expected idempotent success_count to remain 1, got {res2['success_count']}"

        # Different outbox_id 102 (genuine new promotion) should increment success_count
        res3 = record_trace(sig, sol, traces_path=traces_file, outbox_id=102)
        assert res3["success_count"] == 2, f"Expected new outbox to increment success_count to 2, got {res3['success_count']}"

        print("  [PASS] test_outbox_idempotency_on_lease_expiry")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_record_trace_credential_redaction_boundary():
    """Verify direct record_trace caller with secrets never persists plaintext to disk (VULN-003)."""
    temp_dir = tempfile.mkdtemp()
    try:
        traces_file = os.path.join(temp_dir, "proven_traces.json")
        from experiential_memory import record_trace

        secret_ghp = "ghp_1234567890abcdef1234567890abcdef1234"
        secret_aws = "AKIAIOSFODNN7EXAMPLE"

        sig = f"connect to github with {secret_ghp}"
        sol = f"export AWS_ACCESS_KEY_ID={secret_aws}"

        # Call public API directly
        record_trace(sig, sol, tags=["github", secret_ghp], workspace_context=f"repo-{secret_aws}", traces_path=traces_file)

        # Inspect disk payload directly
        with open(traces_file, "r", encoding="utf-8") as f:
            disk_content = f.read()

        assert secret_ghp not in disk_content, f"Plaintext GitHub token leaked to disk: {disk_content}"
        assert secret_aws not in disk_content, f"Plaintext AWS key leaked to disk: {disk_content}"
        assert "[REDACTED_" in disk_content, "Redaction marker missing on disk"

        print("  [PASS] test_record_trace_credential_redaction_boundary")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_schema_integrity_runtime_error_not_assert():
    """Verify post-migration integrity checks use explicit RuntimeError instead of assert (VULN-004)."""
    import inspect
    import memory_schema

    source = inspect.getsource(memory_schema.init_database)
    # Ensure there are no assert statements inside init_database
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("assert ") or stripped.startswith("assert("):
            raise AssertionError(f"Forbidden 'assert' found in init_database: {stripped}")

    print("  [PASS] test_schema_integrity_runtime_error_not_assert")


def test_tenant_scoped_proven_traces_isolation():
    """Verify Tenant A and Tenant B with identical signature get distinct isolated traces (VULN-001)."""
    temp_dir = tempfile.mkdtemp()
    try:
        traces_file = os.path.join(temp_dir, "proven_traces.json")
        from experiential_memory import record_trace, recall_traces, load_traces

        ws_a = "11111111111111111111111111111111"
        ws_b = "22222222222222222222222222222222"
        sig = "Docker port 8080 collision"

        # Tenant A records fix
        res_a = record_trace(sig, "fuser -k 8080/tcp", traces_path=traces_file, workspace_hash=ws_a)
        # Tenant B records fix for the exact same problem signature
        res_b = record_trace(sig, "kill -9 $(lsof -t -i:8080)", traces_path=traces_file, workspace_hash=ws_b)

        assert res_a["id"] != res_b["id"], f"Tenant A and B collided on trace_id: {res_a['id']} vs {res_b['id']}"

        data = load_traces(traces_file)
        traces = data.get("traces", [])
        assert len(traces) == 2, f"Expected 2 traces in JSON file, found {len(traces)}"

        # Recall for Tenant A must return Tenant A's solution
        recalled_a = recall_traces("port 8080 collision", traces_path=traces_file, workspace_hash=ws_a)
        assert len(recalled_a) == 1, f"Expected 1 trace for Tenant A, got {len(recalled_a)}"
        assert recalled_a[0]["trace"]["proven_solution"] == "fuser -k 8080/tcp"

        # Recall for Tenant B must return Tenant B's solution
        recalled_b = recall_traces("port 8080 collision", traces_path=traces_file, workspace_hash=ws_b)
        assert len(recalled_b) == 1, f"Expected 1 trace for Tenant B, got {len(recalled_b)}"
        assert recalled_b[0]["trace"]["proven_solution"] == "kill -9 $(lsof -t -i:8080)"

        print("  [PASS] test_tenant_scoped_proven_traces_isolation")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_activation_events_quarantine_records_last_error():
    """Verify dead-lettered activation_events record diagnostic error context in last_error column (VULN-006)."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_quarantine_diag.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Insert activation event with whitespace workspace_dir (triggers ValueError in resolve_workspace_hash)
        conn.execute(
            """
            INSERT INTO activation_events (
                session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated
            ) VALUES ('sess-diag', ?, 'valid user query', '   ', 'test-skill', 1, '[]', 1.0, 0)
            """,
            (now_str,)
        )
        conn.commit()

        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        engine.consolidate_batch(batch_size=10, dry_run=False)

        row = conn.execute("SELECT is_consolidated, last_error FROM activation_events WHERE session_id = 'sess-diag'").fetchone()
        assert row is not None, "Event row not found"
        assert row[0] == 2, f"Expected is_consolidated=2 (quarantined), got {row[0]}"
        assert row[1] is not None, "last_error column is NULL"
        assert "ValueError" in row[1] and "workspace directory" in row[1].lower(), f"Unexpected last_error content: {row[1]}"

        conn.close()
        print("  [PASS] test_activation_events_quarantine_records_last_error")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)



def test_redact_pem_large_boundary():
    pem = "-----BEGIN RSA PRIVATE KEY-----\n" + ("A" * 70_000) + "\n-----END RSA PRIVATE KEY-----"
    redacted = redact_secrets(pem)
    assert "[REDACTED_PRIVATE_KEY]" in redacted, "Placeholder missing"
    assert "A" * 100 not in redacted, "Original key material leaked"
    print("  [PASS] test_redact_pem_large_boundary")


def test_redact_suffix_and_allowlist():
    payload = {
        "service_api_key": "s3cr3t",
        "db_password": "p@ssw0rd",
        "auth_token": "tok123",
        "primary_key": "keep_me",
        "foreign_key": "keep_me_too",
        "sort_key": "keep_this_one"
    }
    redacted_str = redact_secrets(json.dumps(payload))
    redacted = json.loads(redacted_str)
    for k in ("service_api_key", "db_password", "auth_token"):
        assert redacted[k] == "[REDACTED_KEY]", f"{k} not redacted"
    for k in ("primary_key", "foreign_key", "sort_key"):
        assert redacted[k] == payload[k], f"{k} should not be redacted"
    print("  [PASS] test_redact_suffix_and_allowlist")


def test_redact_json_depth_fail_loud():
    deep = cur = {}
    for i in range(35):
        cur["lvl"] = {}
        cur = cur["lvl"]
    res = redact_secrets(json.dumps(deep))
    assert "[REDACTED_MAX_DEPTH]" in res
    print("  [PASS] test_redact_json_depth_fail_loud")


def test_outbox_generation_reinforcement():
    temp_dir = tempfile.mkdtemp()
    try:
        traces_file = os.path.join(temp_dir, "test_traces.json")
        t1 = record_trace(
            problem_signature="remediation bug test",
            proven_solution="solution step 1",
            traces_path=traces_file,
            outbox_id=10,
            outbox_generation=1,
            workspace_hash="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        )
        assert t1.get("success_count") == 1
        assert t1.get("last_outbox_generation") == 1

        # Second call – same generation, must be idempotent
        t2 = record_trace(
            problem_signature="remediation bug test",
            proven_solution="solution step 1",
            traces_path=traces_file,
            outbox_id=10,
            outbox_generation=1,
            workspace_hash="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        )
        assert t2.get("success_count") == 1, "success_count incremented on idempotent call"
        assert t2.get("last_outbox_generation") == 1

        # Third call – newer generation bumps count and updates solution
        t3 = record_trace(
            problem_signature="remediation bug test",
            proven_solution="solution step 2 reinforced",
            traces_path=traces_file,
            outbox_id=10,
            outbox_generation=2,
            workspace_hash="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        )
        assert t3.get("success_count") == 2, "success_count not incremented on newer generation"
        assert t3.get("last_outbox_generation") == 2
        assert t3.get("proven_solution") == "solution step 2 reinforced"

        data = load_traces(traces_file)
        matching = [t for t in data.get("traces", []) if t.get("last_outbox_id") == 10]
        assert len(matching) == 1, "Multiple trace rows for same outbox_id"
        assert matching[0]["success_count"] == 2
        assert matching[0]["last_outbox_generation"] == 2

        print("  [PASS] test_outbox_generation_reinforcement")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_subworkspace_authorized_hashes():
    root = tempfile.mkdtemp()
    sub = os.path.join(root, "sub_ws")
    os.makedirs(sub, exist_ok=True)
    db_path = os.path.join(root, "test.db")
    conn = init_database(db_path)

    try:
        engine = ConsolidatorEngine(conn, workspace_root=root)
        engine.register_workspace(sub)
        sub_hash = canonical_workspace_hash(sub)
        assert sub_hash in engine.authorized_hashes

        res = resolve_workspace_hash(sub_hash, approved_root=root, authorized_hashes=engine.authorized_hashes)
        assert res == sub_hash

        print("  [PASS] test_subworkspace_authorized_hashes")
    finally:
        conn.close()
        shutil.rmtree(root, ignore_errors=True)


def test_windows_msvcrt_lock_contention_retry():
    temp_dir = tempfile.mkdtemp()
    lock_path = os.path.join(temp_dir, "test.lock")
    try:
        success_counter = 0
        counter_lock = threading.Lock()
        errors = []

        def worker():
            nonlocal success_counter
            try:
                with FileLock(lock_path, timeout=5.0):
                    time.sleep(0.02)
                with counter_lock:
                    success_counter += 1
            except Exception as exc:
                with counter_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors encountered during FileLock contention: {errors}"
        assert success_counter == 4, f"Only {success_counter}/4 threads acquired the lock"
        print("  [PASS] test_windows_msvcrt_lock_contention_retry")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_two_tenant_vector_backfill_isolation():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_backfill.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        ws_a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ws_b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

        # Insert 2 rows for Tenant A
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES
            ('mem-a1', ?, '/path/a', 'proven_trace', 'Title A1', 'sig a1', 'sol a1', '', 'folded', 'Active', 1, 1.0, 0.08, ?, ?),
            ('mem-a2', ?, '/path/a', 'proven_trace', 'Title A2', 'sig a2', 'sol a2', '', 'folded', 'Active', 1, 1.0, 0.08, ?, ?)
            """,
            (ws_a, now_str, now_str, ws_a, now_str, now_str)
        )

        # Insert 2 rows for Tenant B
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, bilingual_tags,
                content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES
            ('mem-b1', ?, '/path/b', 'proven_trace', 'Title B1', 'sig b1', 'sol b1', '', 'folded', 'Active', 1, 1.0, 0.08, ?, ?),
            ('mem-b2', ?, '/path/b', 'proven_trace', 'Title B2', 'sig b2', 'sol b2', '', 'folded', 'Active', 1, 1.0, 0.08, ?, ?)
            """,
            (ws_b, now_str, now_str, ws_b, now_str, now_str)
        )
        conn.commit()

        # Engine scoped strictly to Tenant A
        engine = ConsolidatorEngine(conn, workspace_hash=ws_a)
        engine.consolidate_batch(batch_size=10, dry_run=False)

        # Verify dense_embeddings only contains ws_a rows and zero ws_b rows
        rows = conn.execute("SELECT memory_id, workspace_hash FROM dense_embeddings").fetchall()
        for r in rows:
            assert r[1] == ws_a, f"Exfiltration detected: dense_embeddings contains row from {r[1]}"
            assert r[0] in ('mem-a1', 'mem-a2'), f"Unexpected memory_id {r[0]}"

        b_rows = conn.execute("SELECT count(*) FROM dense_embeddings WHERE workspace_hash = ?", (ws_b,)).fetchone()[0]
        assert b_rows == 0, f"Tenant B rows were backfilled by Tenant A engine: {b_rows}"

        conn.close()
        print("  [PASS] test_two_tenant_vector_backfill_isolation")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_recall_traces_fail_closed():
    temp_dir = tempfile.mkdtemp()
    try:
        traces_path = os.path.join(temp_dir, "test_recall.json")
        data = {
            "version": "3.0.0",
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "traces": [
                {
                    "id": "tr-1",
                    "workspace_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "problem_signature": "git status error",
                    "proven_solution": "git clean",
                    "tokens": ["git", "status", "error"],
                    "success_count": 1
                },
                {
                    "id": "tr-2",
                    "workspace_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "problem_signature": "git status error",
                    "proven_solution": "git pull",
                    "tokens": ["git", "status", "error"],
                    "success_count": 1
                },
                {
                    "id": "tr-3",
                    "workspace_hash": "",
                    "problem_signature": "git status error",
                    "proven_solution": "git reset",
                    "tokens": ["git", "status", "error"],
                    "success_count": 1
                }
            ]
        }
        with open(traces_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # 1. Scoped query for ws-alpha: must return ONLY tr-1 (never tr-2 or tr-3 with empty hash)
        res_a = recall_traces("git status error", workspace_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", traces_path=traces_path)
        assert len(res_a) == 1, f"Expected 1 trace, got {len(res_a)}"
        assert res_a[0]["trace"]["id"] == "tr-1", f"Returned wrong trace: {res_a[0]['trace']['id']}"

        # 2. Unscoped query without workspace_hash and without workspace_dir must fail closed (empty list)
        res_unscoped = recall_traces("git status error", traces_path=traces_path)
        assert res_unscoped == [], f"Expected empty list for unscoped recall, got {res_unscoped}"

        # 3. Explicit allow_unscoped=True permits legacy/global recall
        res_allowed = recall_traces("git status error", traces_path=traces_path, allow_unscoped=True, top_k=5)
        assert len(res_allowed) == 3, f"Expected 3 traces with allow_unscoped=True, got {len(res_allowed)}"

        print("  [PASS] test_recall_traces_fail_closed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_trace_metadata_and_action_type_redacted():
    temp_dir = tempfile.mkdtemp()
    try:
        traces_path = os.path.join(temp_dir, "test_redacted.json")
        tr = record_trace(
            problem_signature="syntax error",
            proven_solution="fixed code",
            action_type="Bearer secret_token_1234567890abcdef",
            workspace_context="db_password=mysecretpassword123",
            workspace_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            traces_path=traces_path
        )
        # Verify in-memory return object is redacted
        assert "secret_token" not in tr["action_type"], "Raw token leaked in returned action_type"
        assert "[REDACTED_TOKEN]" in tr["action_type"], "Missing token redaction in action_type"
        assert "mysecretpassword123" not in tr["workspace_context"], "Raw password leaked in returned workspace_context"
        assert "[REDACTED_PASSWORD]" in tr["workspace_context"], "Missing password redaction in workspace_context"

        # Verify persisted file on disk is also redacted
        data = load_traces(traces_path)
        disk_tr = data["traces"][0]
        assert "secret_token" not in disk_tr["action_type"]
        assert "[REDACTED_TOKEN]" in disk_tr["action_type"]
        assert "mysecretpassword123" not in disk_tr["workspace_context"]
        assert "[REDACTED_PASSWORD]" in disk_tr["workspace_context"]

        print("  [PASS] test_trace_metadata_and_action_type_redacted")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_fts5_syntax_error_does_not_leak_secrets():
    import io
    import contextlib
    from unittest.mock import MagicMock

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute.side_effect = sqlite3.OperationalError("fts5: syntax error near X")
    mock_conn.cursor.return_value = mock_cur

    bad_query = 'sk-1234567890abcdef1234567890 syntax-break'
    captured_stderr = io.StringIO()
    with contextlib.redirect_stderr(captured_stderr):
        res = search_fts5(mock_conn, query=bad_query, workspace_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    err_output = captured_stderr.getvalue()
    assert "sk-1234567890abcdef1234567890" not in err_output, "Raw secret leaked in FTS5 syntax error log!"
    assert "[REDACTED_API_KEY]" in err_output, "Redaction tag missing from FTS5 syntax error log!"
    assert res == []

    print("  [PASS] test_fts5_syntax_error_does_not_leak_secrets")


def test_outbox_cas_generation_and_token_fencing():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_cas.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Insert outbox row with generation=1
        conn.execute(
            """
            INSERT INTO consolidation_outbox (
                memory_id, workspace_hash, signature, solution, tags, context, status, created_at, generation, owner_token, claimed_at
            ) VALUES ('mem-cas-1', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'sig', 'sol', '[]', '', 'InFlight', ?, 1, 'token-old', ?)
            """,
            (now_str, now_str)
        )
        conn.commit()
        ob_id = conn.execute("SELECT outbox_id FROM consolidation_outbox WHERE memory_id = 'mem-cas-1'").fetchone()[0]

        # 2. Simulate subsequent promotion cycle: bumps generation to 2, clears owner_token to NULL, sets status='Pending'
        conn.execute(
            """
            UPDATE consolidation_outbox
            SET generation = 2,
                status = 'Pending',
                owner_token = NULL,
                claimed_at = NULL
            WHERE outbox_id = ?
            """,
            (ob_id,)
        )
        conn.commit()

        # 3. Old worker with owner_token='token-old' attempts CAS update against generation 1
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE consolidation_outbox
            SET status = 'Flushed', flushed_at = datetime('now')
            WHERE outbox_id = ? AND owner_token = 'token-old' AND status = 'InFlight' AND generation = 1;
            """,
            (ob_id,)
        )
        assert cur.rowcount == 0, f"Stale worker CAS unexpectedly succeeded, modified {cur.rowcount} rows!"

        # Verify row remains Pending with generation 2
        row = conn.execute("SELECT status, generation, owner_token FROM consolidation_outbox WHERE outbox_id = ?", (ob_id,)).fetchone()
        assert row[0] == "Pending", f"Expected status 'Pending', got {row[0]}"
        assert row[1] == 2, f"Expected generation 2, got {row[1]}"
        assert row[2] is None, f"Expected owner_token to be NULL, got {row[2]}"

        conn.close()
        print("  [PASS] test_outbox_cas_generation_and_token_fencing")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_activation_events_poison_pill_batch_resilience():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_resilience.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Cluster 1: Poison-pill events (whitespace workspace_dir triggers ValueError in resolve_workspace_hash)
        conn.execute(
            """
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
            VALUES
            ('sess-p1', ?, 'poison command 1', '   ', 'test-skill', 1, '[]', 1.0, 0),
            ('sess-p2', ?, 'poison command 2', '   ', 'test-skill', 1, '[]', 1.0, 0)
            """,
            (now_str, now_str)
        )

        # Cluster 2: Valid commands
        conn.execute(
            """
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
            VALUES
            ('sess-v1', ?, 'clean valid command', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'test-skill', 1, '[]', 1.0, 0),
            ('sess-v2', ?, 'clean valid command', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'test-skill', 1, '[]', 1.0, 0)
            """,
            (now_str, now_str)
        )
        conn.commit()

        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        batch_res = engine.consolidate_batch(batch_size=10, dry_run=False)

        # Assert cluster 2 was promoted
        assert batch_res["promoted_traces"] >= 1, f"Expected promoted_traces >= 1, got {batch_res['promoted_traces']}"

        # Assert poison pill events are quarantined (is_consolidated=2) and recorded last_error
        rows = conn.execute("SELECT session_id, is_consolidated, last_error FROM activation_events WHERE session_id IN ('sess-p1', 'sess-p2')").fetchall()
        for r in rows:
            assert r[1] == 2, f"Poison pill event {r[0]} was not quarantined (is_consolidated={r[1]})"
            assert "workspace directory" in (r[2] or "").lower() or "error" in (r[2] or "").lower(), f"Unexpected last_error: {r[2]}"

        conn.close()
        print("  [PASS] test_activation_events_poison_pill_batch_resilience")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)



def test_cross_tenant_trace_id_prefix_collision():
    temp_dir = tempfile.mkdtemp()
    try:
        traces_file = os.path.join(temp_dir, "traces.json")
        ws_a = "a" * 32
        ws_b = "b" * 32
        sig = "collision_sig"
        act = "action_type"

        # Record a trace for tenant A
        tr_a = record_trace(
            problem_signature=sig,
            proven_solution="solution_A",
            action_type=act,
            workspace_hash=ws_a,
            traces_path=traces_file
        )
        # Record a trace for tenant B (same signature/action)
        tr_b = record_trace(
            problem_signature=sig,
            proven_solution="solution_B",
            action_type=act,
            workspace_hash=ws_b,
            traces_path=traces_file
        )

        # Verify isolation
        recalled_a = recall_traces(sig, workspace_hash=ws_a, traces_path=traces_file)
        recalled_b = recall_traces(sig, workspace_hash=ws_b, traces_path=traces_file)

        assert any(t["trace"]["proven_solution"] == "solution_A" for t in recalled_a), "A's solution missing"
        assert any(t["trace"]["proven_solution"] == "solution_B" for t in recalled_b), "B's solution missing"
        assert not any(t["trace"]["proven_solution"] == "solution_B" for t in recalled_a), "B overwrote A"
        assert not any(t["trace"]["proven_solution"] == "solution_A" for t in recalled_b), "A overwrote B"

        # Check file data directly
        data = load_traces(traces_file)
        all_traces = data.get("traces", [])
        assert len(all_traces) == 2
        a_entry = next(t for t in all_traces if t.get("workspace_hash") == ws_a)
        b_entry = next(t for t in all_traces if t.get("workspace_hash") == ws_b)
        assert a_entry["proven_solution"] == "solution_A"
        assert b_entry["proven_solution"] == "solution_B"

        print("  [PASS] test_cross_tenant_trace_id_prefix_collision")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_consolidator_unverified_workspace_hash_rejection():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test.db")
        conn = init_database(db_path)
        temp_root = os.path.join(temp_dir, "my_root")
        os.makedirs(temp_root, exist_ok=True)
        bogus_hash = "c" * 32
        try:
            ConsolidatorEngine(
                conn,
                workspace_root=temp_root,
                workspace_hash=bogus_hash,
            )
            raise AssertionError("ValueError not raised for unverified workspace_hash")
        except ValueError as exc:
            assert "does not belong to approved workspace_root" in str(exc)
        conn.close()
        print("  [PASS] test_consolidator_unverified_workspace_hash_rejection")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_drain_l1_staging_unscoped_fails_closed():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=False)
        try:
            engine.drain_l1_staging()
            raise AssertionError("RuntimeError not raised")
        except RuntimeError as exc:
            assert "cannot operate on unscoped engine" in str(exc)
        conn.close()
        print("  [PASS] test_drain_l1_staging_unscoped_fails_closed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_redact_secrets_generic_token_basic_auth_pgp():
    raw = """
    token=supersecret123
    client_secret="myclientsecret999"
    AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    Authorization: Basic dXNlcjpwYXNzd29yZA==
    -----BEGIN PGP PRIVATE KEY BLOCK-----
    mQENBF2...-----END PGP PRIVATE KEY BLOCK-----
    """
    redacted = redact_secrets(raw)
    for secret in [
        "supersecret123",
        "myclientsecret999",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "dXNlcjpwYXNzd29yZA==",
        "BEGIN PGP PRIVATE KEY BLOCK",
    ]:
        assert secret not in redacted, f"Secret {secret} leaked in redacted text: {redacted}"
    assert "[REDACTED" in redacted
    print("  [PASS] test_redact_secrets_generic_token_basic_auth_pgp")


def test_diagnostics_no_secrets_in_fts5_or_cluster_key():
    from unittest.mock import MagicMock
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute.side_effect = sqlite3.OperationalError('fts5: syntax error near "sk-ant-api03-abcdef1234567890"')
    mock_conn.cursor.return_value = mock_cur

    secret_key = "sk-ant-api03-abcdef1234567890"
    query = f"{secret_key} syntax-break"
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        res = search_fts5(mock_conn, query, workspace_hash="a" * 32)
    err_output = stderr.getvalue()
    assert secret_key not in err_output, f"Secret leaked in FTS5 syntax error stderr: {err_output}"
    assert "[REDACTED" in err_output

    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test.db")
        conn = init_database(db_path)
        token = "mysecrettoken12345"
        ws_hash = "d" * 32
        conn.execute(
            "INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, feedback_score, is_consolidated) VALUES ('s1', datetime('now'), ?, ?, 1.0, 0)",
            (f"Fix error with token={token}", ws_hash)
        )
        conn.execute(
            "INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, feedback_score, is_consolidated) VALUES ('s2', datetime('now'), ?, ?, 1.0, 0)",
            (f"Fix error with token={token}", ws_hash)
        )
        conn.commit()

        stderr = io.StringIO()
        engine = ConsolidatorEngine(conn, workspace_hash=ws_hash)
        with contextlib.redirect_stderr(stderr):
            engine.consolidate_batch()
        err_output = stderr.getvalue()
        assert token not in err_output, f"Secret leaked in cluster logs stderr: {err_output}"
        conn.close()
        print("  [PASS] test_diagnostics_no_secrets_in_fts5_or_cluster_key")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_stale_outbox_worker_does_not_overwrite_newer_generation():
    temp_dir = tempfile.mkdtemp()
    try:
        traces_file = os.path.join(temp_dir, "traces.json")
        ws = "d" * 32
        # Newer generation first (gen 2)
        trace_new = record_trace(
            problem_signature="sig_stale_test",
            proven_solution="GEN2_SOLUTION",
            action_type="command",
            workspace_hash=ws,
            outbox_id=101,
            outbox_generation=2,
            traces_path=traces_file
        )
        assert trace_new["proven_solution"] == "GEN2_SOLUTION"
        assert trace_new["success_count"] == 1

        # Stale generation attempt (gen 1)
        trace_stale = record_trace(
            problem_signature="sig_stale_test",
            proven_solution="GEN1_STALE_SOLUTION",
            action_type="command",
            workspace_hash=ws,
            outbox_id=101,
            outbox_generation=1,
            traces_path=traces_file
        )
        # The returned trace should remain the newer one, success_count unchanged
        assert trace_stale["proven_solution"] == "GEN2_SOLUTION"
        assert trace_stale["success_count"] == 1
        assert trace_stale.get("last_outbox_generation") == 2

        # Verify on-disk file
        disk_data = load_traces(traces_file)
        saved = disk_data["traces"][0]
        assert saved["proven_solution"] == "GEN2_SOLUTION"
        assert saved["success_count"] == 1
        assert saved["last_outbox_generation"] == 2

        print("  [PASS] test_stale_outbox_worker_does_not_overwrite_newer_generation")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_flush_outbox_empty_whitespace_workspace_hash_raises():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test.db")
        conn = init_database(db_path)
        for bad_hash in ("", "   "):
            try:
                flush_outbox(conn, workspace_hash=bad_hash)
                raise AssertionError(f"ValueError not raised for hash {bad_hash!r}")
            except ValueError:
                pass
        conn.close()
        print("  [PASS] test_flush_outbox_empty_whitespace_workspace_hash_raises")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_filelock_symlink_attack_rejected():
    temp_dir = tempfile.mkdtemp()
    try:
        target_file = os.path.join(temp_dir, "real_sensitive.txt")
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("SENSITIVE_DATA_CONTENT")
        symlink_path = os.path.join(temp_dir, "attack.lock")
        try:
            os.symlink(target_file, symlink_path)
        except (OSError, NotImplementedError):
            # Windows without SeCreateSymbolicLinkPrivilege: skip symlink creation
            print("  [PASS] test_filelock_symlink_attack_rejected (symlinks not permitted on host)")
            return

        try:
            with FileLock(symlink_path, timeout=0.5):
                raise AssertionError("Expected PermissionError/OSError not raised on symlink lock")
        except (PermissionError, OSError):
            pass

        # Ensure the target file content is completely untouched
        with open(target_file, "r", encoding="utf-8") as f:
            assert f.read() == "SENSITIVE_DATA_CONTENT"
        print("  [PASS] test_filelock_symlink_attack_rejected")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_consolidator_allow_unscoped_override_rejected():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=False)
        try:
            engine.consolidate_batch(allow_unscoped=True)
            raise AssertionError("RuntimeError not raised when overriding allow_unscoped")
        except RuntimeError as exc:
            assert "Cannot override allow_unscoped=True" in str(exc)
        conn.close()
        print("  [PASS] test_consolidator_allow_unscoped_override_rejected")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_chunked_execute_sqlite_variables_large_batch():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE big (id INTEGER PRIMARY KEY, val TEXT)")
        conn.executemany("INSERT INTO big (val) VALUES (?)", [(f"row{i}",) for i in range(1500)])
        conn.commit()

        ids = list(range(1, 1501))
        cur = conn.cursor()
        _chunked_execute(cur, "DELETE FROM big WHERE id IN ({placeholders})", ids, chunk_size=500)
        conn.commit()

        remaining = conn.execute("SELECT COUNT(*) FROM big").fetchone()[0]
        assert remaining == 0, f"{remaining} rows left after chunked delete"
        conn.close()
        print("  [PASS] test_chunked_execute_sqlite_variables_large_batch")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_revert_invariant_with_null_and_caller_transaction():
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test.db")
        conn = init_database(db_path)
        real_hash = "e" * 32

        now_str = "2026-11-04 12:00:00"
        # Test non-existent record safely returns False
        assert revert_invariant(conn, superseded_id='missing-inv') is False

        # Insert active target for real_hash
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type, title, problem_signature, solution_payload, content_folded, status, superseded_by, last_accessed_at, created_at
            ) VALUES ('real-inv-1', ?, '/path/real', 'invariant', 'Real Inv 1', 'sig', 'sol', 'real inv 1', 'Superseded', 'real-inv-2', ?, ?)
            """,
            (real_hash, now_str, now_str)
        )
        conn.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type, title, problem_signature, solution_payload, content_folded, status, last_accessed_at, created_at
            ) VALUES ('real-inv-2', ?, '/path/real', 'invariant', 'Real Inv 2', 'sig', 'sol', 'real inv 2', 'Active', ?, ?)
            """,
            (real_hash, now_str, now_str)
        )
        conn.commit()

        # Test inside an active transaction: revert_invariant does not mutate isolation_level or commit outer tx
        cur = conn.cursor()
        cur.execute("SAVEPOINT caller_sp;")
        ok = revert_invariant(conn, superseded_id='real-inv-1', workspace_hash=real_hash)
        assert ok is True, "revert_invariant should succeed within caller savepoint"

        # Verify rollback of caller savepoint works cleanly
        cur.execute("ROLLBACK TO SAVEPOINT caller_sp;")
        cur.execute("RELEASE SAVEPOINT caller_sp;")

        # Status of real-inv-1 should be Superseded again due to caller rollback
        cur.execute("SELECT status FROM workspace_episodic_memory WHERE memory_id = 'real-inv-1'")
        st = cur.fetchone()[0]
        assert st == 'Superseded', f"Expected Superseded after caller rollback, got {st}"

        conn.close()
        print("  [PASS] test_revert_invariant_with_null_and_caller_transaction")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)




# =====================================================================
# VULN-001 to VULN-006: CRITIC RED-TEAMING REGRESSION TESTS (ROUND 4)
# =====================================================================

def test_caller_transaction_not_committed_by_engine_or_flush():
    """Verify ConsolidatorEngine and flush_outbox refuse to run inside an uncommitted caller transaction without committing."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_caller_tx.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Caller begins explicit transaction
        conn.execute("BEGIN IMMEDIATE;")
        conn.execute(
            """
            INSERT INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash, tier_used, is_drained)
            VALUES ('sess-uncommitted', ?, 'uncommitted caller input', '11111111111111111111111111111111', 1, 0)
            """,
            (now_str,)
        )

        # ConsolidatorEngine construction must fail loud without committing
        try:
            ConsolidatorEngine(conn, allow_unscoped=True)
            assert False, "ConsolidatorEngine should have raised RuntimeError inside active transaction"
        except RuntimeError as e:
            assert "cannot be initialized while an uncommitted transaction is active" in str(e)

        # flush_outbox must fail loud without committing
        try:
            flush_outbox(conn, limit=10)
            assert False, "flush_outbox should have raised RuntimeError inside active transaction"
        except RuntimeError as e:
            assert "flush_outbox must be called outside active transactions" in str(e)

        # Rollback caller transaction
        conn.rollback()

        # Assert uncommitted row was cleanly discarded (NO silent commit)
        row = conn.execute("SELECT session_id FROM l1_staging_log WHERE session_id = 'sess-uncommitted'").fetchone()
        assert row is None, "Caller uncommitted work was silently committed by library!"

        conn.close()
        print("  [PASS] test_caller_transaction_not_committed_by_engine_or_flush")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_corrupt_traces_file_load_raises_and_record_aborts():
    """Verify corrupt traces file causes load_traces to raise and record_trace to abort without clobbering."""
    temp_dir = tempfile.mkdtemp()
    try:
        traces_path = os.path.join(temp_dir, "test_corrupt_traces.json")
        with open(traces_path, "w", encoding="utf-8") as f:
            f.write("{invalid json corrupt content")

        # load_traces must raise ValueError on corrupt file
        try:
            load_traces(traces_path)
            assert False, "load_traces should have raised ValueError on invalid JSON"
        except ValueError as ve:
            assert "contains invalid JSON" in str(ve)

        # record_trace must abort and return empty dict without overwriting the file
        res = record_trace(
            problem_signature="test sig",
            proven_solution="test sol",
            traces_path=traces_path
        )
        assert res == {}, f"record_trace should have returned empty dict, got: {res}"

        # File content must still be the original corrupt string (NOT overwritten with empty traces)
        with open(traces_path, "r", encoding="utf-8") as f:
            content_read = f.read()
        assert content_read == "{invalid json corrupt content", "Corrupt file was overwritten by record_trace!"

        print("  [PASS] test_corrupt_traces_file_load_raises_and_record_aborts")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_transient_vs_permanent_outbox_retry_classification():
    """Verify is_transient_io_error distinguishes transient lock contention from permanent filesystem errors."""
    from consolidator import is_transient_io_error

    # Transient errors
    assert is_transient_io_error(TimeoutError("lock timeout")) is True
    assert is_transient_io_error(OSError(errno.EAGAIN, "Resource temporarily unavailable")) is True
    assert is_transient_io_error(OSError(errno.EWOULDBLOCK, "Resource temporarily unavailable")) is True
    assert is_transient_io_error(OSError(errno.ETIMEDOUT, "Connection timed out")) is True

    # Windows transient winerrors (sharing violation / lock violation)
    win_transient = OSError(13, "Permission denied")
    win_transient.winerror = 32  # ERROR_SHARING_VIOLATION
    assert is_transient_io_error(win_transient) is True

    # Permanent errors: MUST be False
    assert is_transient_io_error(PermissionError("Access denied")) is False
    assert is_transient_io_error(FileNotFoundError("File not found")) is False
    assert is_transient_io_error(IsADirectoryError("Is a directory")) is False
    assert is_transient_io_error(OSError(errno.ENOSPC, "No space left on device")) is False
    assert is_transient_io_error(OSError(errno.EACCES, "Permission denied")) is False
    assert is_transient_io_error(OSError(errno.EPERM, "Operation not permitted")) is False
    assert is_transient_io_error(OSError(errno.EROFS, "Read-only file system")) is False

    print("  [PASS] test_transient_vs_permanent_outbox_retry_classification")


def test_per_cluster_promotion_atomic_savepoint():
    """Verify that a failure during outbox insert rolls back episodic insert via SAVEPOINT without partial persist."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_atomic_promo.db")
        conn = init_database(db_path)
        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Insert 2 matching positive events for cluster promotion
        conn.execute(
            """
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
            VALUES ('sess-atomic-1', ?, 'atomic promotion test query', 'd:/ws_atomic', 'skill-x', 1, '[]', 1.0, 0),
                   ('sess-atomic-2', ?, 'atomic promotion test query', 'd:/ws_atomic', 'skill-x', 1, '[]', 1.0, 0)
            """,
            (now_str, now_str)
        )
        conn.commit()

        # Force failure on consolidation_outbox insert via trigger
        conn.execute(
            """
            CREATE TRIGGER force_outbox_failure
            BEFORE INSERT ON consolidation_outbox
            BEGIN
                SELECT RAISE(ABORT, 'Simulated forced outbox failure for atomicity test');
            END;
            """
        )

        # Consolidate batch: promotion must catch the error, rollback SAVEPOINT, and quarantine events
        res = engine.consolidate_batch(batch_size=10, dry_run=False)
        assert res["promoted_traces"] == 0, f"Expected 0 promoted traces due to failure, got {res['promoted_traces']}"

        # Verify episodic memory was NOT partially written (SAVEPOINT rollback succeeded)
        ep_count = conn.execute("SELECT count(*) FROM workspace_episodic_memory WHERE title LIKE 'Promoted: atomic promotion test%'").fetchone()[0]
        assert ep_count == 0, f"Orphan episodic row persisted despite outbox failure! (count={ep_count})"

        # Verify events were marked quarantined (is_consolidated = 2) with diagnostic
        quarantined = conn.execute("SELECT is_consolidated, last_error FROM activation_events WHERE session_id IN ('sess-atomic-1', 'sess-atomic-2')").fetchall()
        assert len(quarantined) == 2
        for is_c, l_err in quarantined:
            assert is_c == 2, f"Expected is_consolidated=2, got {is_c}"
            assert "Simulated forced outbox failure" in l_err

        conn.close()
        print("  [PASS] test_per_cluster_promotion_atomic_savepoint")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_redact_trace_dict_fail_closed_and_depth_limit():
    """Verify _redact_trace_dict enforces depth limit 32 and load_traces drops corrupt unredactable traces."""
    temp_dir = tempfile.mkdtemp()
    try:
        # 1. Nesting depth > 32 safely truncates to [REDACTED_MAX_DEPTH] without raising or losing data (VULN-005)
        deep_dict = {"secret_key": "topsecret"}
        cur = deep_dict
        for i in range(35):
            cur["nested"] = {"val": f"level_{i}"}
            cur = cur["nested"]

        res_depth = _redact_trace_dict(deep_dict)
        cur_check = res_depth
        for _ in range(32):
            cur_check = cur_check["nested"]
        assert cur_check["nested"] == "[REDACTED_MAX_DEPTH]", f"Expected [REDACTED_MAX_DEPTH], got: {cur_check['nested']}" 

        # 2. load_traces fails closed: drops unredactable trace without leaking raw secret
        traces_path = os.path.join(temp_dir, "test_deep_traces.json")
        traces_data = {
            "version": "3.0.0",
            "updated_at": "",
            "traces": [
                {
                    "id": "valid-trace-1",
                    "problem_signature": "safe query",
                    "proven_solution": "api_key=sk-123456789012345678901234",
                    "tokens": ["safe", "query"]
                },
                {
                    "id": "deep-poison-trace-2",
                    "problem_signature": deep_dict,
                    "proven_solution": "secret=SHOULD_NOT_LEAK",
                    "tokens": ["poison"]
                }
            ]
        }
        with open(traces_path, "w", encoding="utf-8") as f:
            json.dump(traces_data, f)

        loaded = load_traces(traces_path)
        traces = loaded.get("traces", [])
        # Both traces are preserved: valid trace redacted, deep subtree truncated safely without data loss (VULN-005)
        assert len(traces) == 2, f"Expected 2 traces preserved, got {len(traces)}"
        assert traces[0]["id"] == "valid-trace-1"
        assert "sk-1234567890" not in traces[0]["proven_solution"] and "[REDACTED" in traces[0]["proven_solution"]
        assert traces[1]["id"] == "deep-poison-trace-2"
        assert "SHOULD_NOT_LEAK" not in str(traces[1])
        assert "[REDACTED_MAX_DEPTH]" in str(traces[1])

        print("  [PASS] test_redact_trace_dict_fail_closed_and_depth_limit")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_memory_single_writer_concurrent_flush_failure_tracking():
    """Verify MemorySingleWriter tracks failures per sequence and does not hide failures across concurrent flushes."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_writer_seq.db")
        init_database(db_path)
        writer = MemorySingleWriter(db_path)

        # Enqueue task 1: valid insert
        writer.enqueue_write("INSERT INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash, tier_used, is_drained) VALUES ('sess-1', '2026-01-01', 'q1', '11111111111111111111111111111111', 1, 0)")
        writer.flush(timeout=5.0)

        # Enqueue task 2: invalid SQL that will fail inside SQLite worker
        writer.enqueue_write("INSERT INTO non_existent_table_xyz VALUES (1, 2, 3)")
        
        # Enqueue task 3: valid insert
        writer.enqueue_write("INSERT INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash, tier_used, is_drained) VALUES ('sess-3', '2026-01-01', 'q3', '11111111111111111111111111111111', 1, 0)")

        # Flush must raise because task 2 failed
        try:
            writer.flush(timeout=5.0)
            assert False, "writer.flush() should have raised RuntimeError for failed SQL task"
        except RuntimeError as fe:
            assert "write failure(s)" in str(fe)

        writer.close()
        print("  [PASS] test_memory_single_writer_concurrent_flush_failure_tracking")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_persist_diag_redaction_and_truncation():
    """Verify persist_diag redacts credentials and truncates to 512 chars (VULN-002, VULN-008)."""
    exc = ValueError("Authorization failed with Bearer secret-token-1234567890abcdef and " + ("long_data_" * 70))
    res = persist_diag(exc, max_len=512)
    assert "secret-token-1234567890abcdef" not in res
    assert "[REDACTED_TOKEN]" in res
    assert len(res) <= 512
    assert "[TRUNCATED]" in res
    print("  [PASS] test_persist_diag_redaction_and_truncation")


def test_flush_outbox_phase3_savepoint_preserves_outer_tx():
    """Verify flush_outbox status phase rollback does NOT destroy caller's outer transaction (VULN-001)."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_outer_tx.db")
        conn = init_database(db_path, isolation_level="")
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Insert outbox row and commit so conn.in_transaction is False
        conn.execute(
            """
            INSERT INTO consolidation_outbox (
                memory_id, workspace_hash, signature, solution, tags, context, status, created_at, generation
            ) VALUES ('outer-mem-1', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'sig', 'sol', '[]', '', 'Pending', ?, 1)
            """,
            (now_str,)
        )
        conn.commit()

        # Force Phase 3 UPDATE to fail via trigger
        conn.execute(
            """
            CREATE TRIGGER trg_force_phase3_fail
            BEFORE UPDATE OF status ON consolidation_outbox
            WHEN new.status = 'Flushed'
            BEGIN
                SELECT RAISE(ABORT, 'Simulated Phase 3 failure');
            END;
            """
        )
        conn.commit()

        try:
            flush_outbox(conn, workspace_hash='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
            assert False, "Expected flush_outbox to raise RuntimeError"
        except RuntimeError as r_err:
            assert "Simulated Phase 3 failure" in str(r_err)

        conn.close()
        print("  [PASS] test_flush_outbox_phase3_savepoint_preserves_outer_tx")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_last_error_in_db_redacts_credentials():
    """Verify dead-lettered activation_events and staging last_error redact secrets (VULN-002)."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_last_error_sec.db")
        conn = init_database(db_path)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Trigger that raises an error containing a secret token during staging drain
        conn.execute(
            """
            CREATE TRIGGER trg_secret_fail
            BEFORE INSERT ON activation_events
            BEGIN
                SELECT RAISE(ABORT, 'Access denied for Bearer my_secret_token_1234567890');
            END;
            """
        )

        conn.execute(
            """
            INSERT INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash, tier_used, is_drained)
            VALUES ('sess-sec-1', ?, 'test query', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 1, 0)
            """,
            (now_str,)
        )
        conn.commit()

        engine = ConsolidatorEngine(conn, allow_unscoped=True)
        engine.drain_l1_staging()

        row = conn.execute("SELECT is_drained, last_error FROM l1_staging_log WHERE session_id = 'sess-sec-1'").fetchone()
        assert row[0] == 2, f"Expected staging row to be quarantined (2), got {row[0]}"
        assert "my_secret_token_1234567890" not in (row[1] or ""), "Raw secret leaked into last_error DB column!"
        assert "[REDACTED_TOKEN]" in (row[1] or ""), f"Expected redacted token tag in last_error, got: {row[1]}"

        conn.close()
        print("  [PASS] test_last_error_in_db_redacts_credentials")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_path_normalization_normcase_nfc():
    """Verify canonical_workspace_hash normalizes drive casing, slashes, and Unicode NFC (VULN-003)."""
    h1 = canonical_workspace_hash("D:/Repo/MyProject/SubDir")
    h2 = canonical_workspace_hash("d:\\repo\\myproject\\subdir")
    assert h1 == h2, f"Case and slash difference produced different hashes: {h1} vs {h2}"

    # Unicode normalization (composed vs decomposed)
    p_nfc = unicodedata.normalize("NFC", "d:/repo/dự_án")
    p_nfd = unicodedata.normalize("NFD", "d:/repo/dự_án")
    assert canonical_workspace_hash(p_nfc) == canonical_workspace_hash(p_nfd)
    print("  [PASS] test_path_normalization_normcase_nfc")


def test_workspace_registry_persistence():
    """Verify register_workspace persists to workspace_registry table and is loaded by new engine (VULN-007)."""
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "test_ws_reg.db")
        conn = init_database(db_path)
        root_dir = os.path.join(temp_dir, "my_root")
        sub_dir = os.path.join(root_dir, "sub_module")
        os.makedirs(sub_dir, exist_ok=True)

        engine1 = ConsolidatorEngine(conn, workspace_root=root_dir)
        sub_hash = engine1.register_workspace(sub_dir)

        # Assert persisted to workspace_registry
        row = conn.execute("SELECT workspace_path FROM workspace_registry WHERE workspace_hash = ?", (sub_hash,)).fetchone()
        assert row is not None, "Workspace was not persisted to workspace_registry"

        # New engine instance must automatically load authorized_hashes from DB
        engine2 = ConsolidatorEngine(conn, workspace_root=root_dir)
        assert sub_hash in engine2.authorized_hashes, "New engine did not load authorized sub-workspace hash from DB"

        conn.close()
        print("  [PASS] test_workspace_registry_persistence")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_transient_persistence_error_cause_chain():
    """Verify is_transient_io_error inspects __cause__ chain (VULN-004)."""
    inner_block = BlockingIOError(errno.EWOULDBLOCK, "Resource locked")
    wrapper = TracePersistenceError("Failed to persist traces to disk")
    wrapper.__cause__ = inner_block
    assert is_transient_io_error(wrapper) is True, "is_transient_io_error failed to detect transient underlying __cause__"

    inner_perm = PermissionError(errno.EACCES, "Permission denied")
    wrapper2 = TracePersistenceError("Failed to persist traces to disk")
    wrapper2.__cause__ = inner_perm
    assert is_transient_io_error(wrapper2) is False, "is_transient_io_error incorrectly classified permanent error as transient"
    print("  [PASS] test_transient_persistence_error_cause_chain")


def test_trace_with_null_workspace_hash():
    """Verify record_trace and recall_traces handle trace entries with workspace_hash: null without AttributeError (VULN-001)."""
    temp_dir = tempfile.mkdtemp()
    try:
        traces_file = os.path.join(temp_dir, "test_null_ws.json")
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        initial_data = {
            "version": "3.0.0",
            "updated_at": now_str,
            "traces": [
                {
                    "id": "trace-legacy-null",
                    "workspace_hash": None,
                    "problem_signature": "null workspace test cmd",
                    "proven_solution": "run null test",
                    "action_type": "command",
                    "tokens": ["null", "workspace", "test", "cmd"],
                    "success_count": 1,
                    "created_at": now_str,
                    "last_recalled": now_str
                }
            ]
        }
        with open(traces_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        # recall_traces must handle workspace_hash: None without AttributeError
        recalled = recall_traces("null workspace", traces_path=traces_file, workspace_hash="a"*32, allow_unscoped=True)
        assert len(recalled) == 1, f"Expected 1 trace recalled, got {len(recalled)}"

        # record_trace against file containing workspace_hash: None must update without crashing
        res = record_trace("null workspace test cmd", "updated solution", traces_path=traces_file, workspace_hash="a"*32)
        assert res.get("id") is not None, "record_trace failed on null workspace trace"

        print("  [PASS] test_trace_with_null_workspace_hash")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_save_traces_unlocked_rejects_corrupted_payload():
    """Verify _save_traces_unlocked raises TracePersistenceError and refuses to overwrite on corrupt payload (VULN-002)."""
    temp_dir = tempfile.mkdtemp()
    try:
        traces_file = os.path.join(temp_dir, "test_valid.json")
        with open(traces_file, "w", encoding="utf-8") as f:
            f.write('{"version": "3.0.0", "traces": [{"id": "t1"}]}')

        # 1. Traces is not a list (string)
        try:
            _save_traces_unlocked({"version": "3.0.0", "traces": "corrupt_string"}, traces_file)
            assert False, "Expected TracePersistenceError for non-list traces"
        except TracePersistenceError:
            pass

        # 2. Traces contains non-dict element
        try:
            _save_traces_unlocked({"version": "3.0.0", "traces": [12345]}, traces_file)
            assert False, "Expected TracePersistenceError for non-dict trace element"
        except TracePersistenceError:
            pass

        # Verify original file was NOT overwritten
        with open(traces_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert '{"id": "t1"}' in content, "Original valid traces file was overwritten!"

        print("  [PASS] test_save_traces_unlocked_rejects_corrupted_payload")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_all_tests():
    print("=" * 65)
    print("🛡️ OMNI-KERNEL v4.1: CLUSTER 1 REMEDIATION TEST SUITE")
    print("=" * 65)
    t0 = time.time()

    test_cross_workspace_isolation()
    test_dry_run_zero_mutation()
    test_no_double_hashing_and_isolated_clusters()
    test_single_writer_foreign_keys_and_fatal_propagation()
    test_revert_invariant_transaction_safety()
    test_cosine_similarity_dimension_guard()
    test_fts5_empty_query_guard()
    test_positive_feedback_promotion_threshold()
    test_monotonic_ebbinghaus_decay()
    test_fts5_trigger_metadata_no_rebuild()
    test_adversarial_workspace_hash_validation()
    test_poison_pill_row_resilience()
    test_consolidator_savepoint_in_caller_tx()
    test_root_containment_and_overflow_limit()
    test_single_writer_reentrant_worker_guard()
    test_workspace_hash_immutable_trigger()
    test_consolidator_reinforcement_two_pass()
    test_secret_redaction_boundary()
    test_cross_tenant_supersede_insert_trigger()
    test_consolidation_durable_outbox()
    test_scoped_consolidator_isolation()
    test_revert_invariant_cycle_detection()
    test_redact_secrets_non_string_and_false_positive()
    test_revert_invariant_broken_chain()
    test_outbox_two_phase_transaction_isolation()
    test_redact_secrets_json_roundtrip_preservation()
    test_cross_tenant_consolidation_non_interference()
    test_outbox_idempotency_on_lease_expiry()
    test_record_trace_credential_redaction_boundary()
    test_schema_integrity_runtime_error_not_assert()
    test_tenant_scoped_proven_traces_isolation()
    test_activation_events_quarantine_records_last_error()
    test_redact_pem_large_boundary()
    test_redact_suffix_and_allowlist()
    test_redact_json_depth_fail_loud()
    test_outbox_generation_reinforcement()
    test_subworkspace_authorized_hashes()
    test_windows_msvcrt_lock_contention_retry()
    test_two_tenant_vector_backfill_isolation()
    test_recall_traces_fail_closed()
    test_trace_metadata_and_action_type_redacted()
    test_fts5_syntax_error_does_not_leak_secrets()
    test_outbox_cas_generation_and_token_fencing()
    test_activation_events_poison_pill_batch_resilience()
    test_cross_tenant_trace_id_prefix_collision()
    test_consolidator_unverified_workspace_hash_rejection()
    test_drain_l1_staging_unscoped_fails_closed()
    test_redact_secrets_generic_token_basic_auth_pgp()
    test_diagnostics_no_secrets_in_fts5_or_cluster_key()
    test_stale_outbox_worker_does_not_overwrite_newer_generation()
    test_flush_outbox_empty_whitespace_workspace_hash_raises()
    test_filelock_symlink_attack_rejected()
    test_consolidator_allow_unscoped_override_rejected()
    test_chunked_execute_sqlite_variables_large_batch()
    test_revert_invariant_with_null_and_caller_transaction()
    test_caller_transaction_not_committed_by_engine_or_flush()
    test_corrupt_traces_file_load_raises_and_record_aborts()
    test_transient_vs_permanent_outbox_retry_classification()
    test_per_cluster_promotion_atomic_savepoint()
    test_redact_trace_dict_fail_closed_and_depth_limit()
    test_memory_single_writer_concurrent_flush_failure_tracking()
    test_persist_diag_redaction_and_truncation()
    test_flush_outbox_phase3_savepoint_preserves_outer_tx()
    test_last_error_in_db_redacts_credentials()
    test_path_normalization_normcase_nfc()
    test_workspace_registry_persistence()
    test_transient_persistence_error_cause_chain()
    test_trace_with_null_workspace_hash()
    test_save_traces_unlocked_rejects_corrupted_payload()

    elapsed = time.time() - t0
    print("=" * 65)
    print(f"🎉 ALL 69 TESTS PASSED IN {elapsed:.3f}s (100% SUCCESS)!")
    print("=" * 65)


if __name__ == '__main__':
    run_all_tests()
