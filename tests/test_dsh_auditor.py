"""Comprehensive test suite for scripts/dsh_auditor.py.

Covers LockManager, ProvenanceLedger, DynamicWorkspaceResolver,
ContextInjector, SessionManager, NDJSONStreamParser, streaming subprocess,
and DSHAuditorClient.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure root directory is on sys.path so scripts.dsh_auditor can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import dsh_auditor as da


# ==============================================================================
# 1. LockManager Tests
# ==============================================================================


class TestLockManager:
    """Tests for LockManager concurrency and safety controls."""

    def test_atomic_acquire_and_release(self, tmp_path: Path) -> None:
        mgr = da.LockManager(repo_root=tmp_path)
        session_id = "sess_atomic_01"

        acquired = mgr.acquire(session_id=session_id)
        assert acquired is True
        assert mgr.lock_path.exists()

        with open(mgr.lock_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["session_id"] == session_id
        assert data["pid"] == os.getpid()
        assert data["scope"] == "tier_1_in_place"
        assert "nonce" in data

        released = mgr.release()
        assert released is True
        assert not mgr.lock_path.exists()

    def test_contention_raises_lock_contention_error_when_alive_pid_holds_lock(
        self, tmp_path: Path
    ) -> None:
        mgr = da.LockManager(repo_root=tmp_path)

        now_iso = datetime.now(timezone.utc).isoformat()
        foreign_payload = {
            "session_id": "foreign_sess",
            "scope": "tier_1_in_place",
            "pid": 999999,
            "hostname": "test-host",
            "acquired_at": now_iso,
            "heartbeat_at": now_iso,
            "timeout_sec": 120.0,
            "nonce": "foreign_nonce",
            "lock_version": "1.1",
            "agent": "dsh",
        }
        mgr.lock_path.write_text(json.dumps(foreign_payload), encoding="utf-8")

        with patch.object(da, "is_process_alive", return_value=True):
            with pytest.raises(da.LockContentionError):
                mgr.acquire(
                    session_id="local_sess",
                    retry_deadline_sec=0.15,
                    base_backoff_sec=0.02,
                )

    def test_zero_byte_stale_lockfile_purged_and_acquired(self, tmp_path: Path) -> None:
        mgr = da.LockManager(repo_root=tmp_path)
        mgr.lock_path.write_text("", encoding="utf-8")

        # Make lockfile older than 5s
        old_mtime = time.time() - 10.0
        os.utime(mgr.lock_path, (old_mtime, old_mtime))

        acquired = mgr.acquire(session_id="sess_after_0byte", retry_deadline_sec=0.2)
        assert acquired is True
        assert mgr.lock_path.exists()
        assert mgr.lock_path.stat().st_size > 0
        mgr.release()

    def test_expired_lock_with_dead_pid_reclaimed(self, tmp_path: Path) -> None:
        mgr = da.LockManager(repo_root=tmp_path)

        old_iso = (datetime.now(timezone.utc) - timedelta(seconds=500)).isoformat()
        expired_payload = {
            "session_id": "dead_sess",
            "scope": "tier_1_in_place",
            "pid": 888888,
            "hostname": "test-host",
            "acquired_at": old_iso,
            "heartbeat_at": old_iso,
            "timeout_sec": 60.0,
            "nonce": "dead_nonce",
            "lock_version": "1.1",
            "agent": "dsh",
        }
        mgr.lock_path.write_text(json.dumps(expired_payload), encoding="utf-8")

        with patch.object(da, "is_process_alive", return_value=False):
            acquired = mgr.acquire(
                session_id="new_sess",
                timeout_sec=60.0,
                retry_deadline_sec=0.2,
            )
            assert acquired is True
            assert mgr.current_payload is not None
            assert mgr.current_payload.session_id == "new_sess"

        mgr.release()

    def test_release_refuses_to_unlink_if_overwritten(self, tmp_path: Path) -> None:
        mgr = da.LockManager(repo_root=tmp_path)
        mgr.acquire(session_id="orig_sess", retry_deadline_sec=0.2)
        assert mgr.lock_path.exists()

        # Simulate another session clobbering the lock file
        foreign_payload = {
            "session_id": "usurper_sess",
            "scope": "tier_1_in_place",
            "pid": 777777,
            "hostname": "other-host",
            "acquired_at": time.time(),
            "heartbeat_at": time.time(),
            "timeout_sec": 120.0,
            "nonce": "different_nonce",
            "lock_version": "1.1",
            "agent": "dsh",
        }
        mgr.lock_path.write_text(json.dumps(foreign_payload), encoding="utf-8")

        released = mgr.release()
        assert released is False
        assert mgr.lock_path.exists()


# ==============================================================================
# 2. ProvenanceLedger Tests
# ==============================================================================


class TestProvenanceLedger:
    """Tests for file provenance tracking, delta computation, and rollbacks."""

    def test_should_ignore_patterns(self, tmp_path: Path) -> None:
        ledger = da.ProvenanceLedger()

        assert ledger.should_ignore(tmp_path / ".git" / "HEAD") is True
        assert ledger.should_ignore(tmp_path / "scratch" / "file.txt") is True
        assert ledger.should_ignore(tmp_path / "pkg" / "__pycache__" / "mod.pyc") is True
        assert ledger.should_ignore(tmp_path / ".pytest_cache" / "v" / "cache") is True
        assert ledger.should_ignore(tmp_path / "mod.pyc") is True
        assert ledger.should_ignore(tmp_path / ".dsh_audit.lock") is True
        assert ledger.should_ignore(tmp_path / ".agy_provenance.jsonl") is True

        assert ledger.should_ignore(tmp_path / "scripts" / "dsh_auditor.py") is False
        assert ledger.should_ignore(tmp_path / "README.md") is False

    def test_take_snapshot_mtime_cache_optimization(self, tmp_path: Path) -> None:
        ledger = da.ProvenanceLedger()
        test_file = tmp_path / "sample.py"
        test_file.write_text("print('hello')", encoding="utf-8")

        mtime_cache: dict[str, tuple[str, float]] = {}
        snap1 = ledger.take_snapshot(tmp_path, mtime_cache=mtime_cache)
        rel_path = "sample.py"
        assert rel_path in snap1
        hash1, mtime1 = snap1[rel_path]

        with patch("hashlib.sha256") as mock_sha:
            snap2 = ledger.take_snapshot(tmp_path, mtime_cache=mtime_cache)
            assert snap2[rel_path] == (hash1, mtime1)
            mock_sha.assert_not_called()

        # Mutate file and verify hash is recalculated
        time.sleep(0.02)
        test_file.write_text("print('world')", encoding="utf-8")
        snap3 = ledger.take_snapshot(tmp_path, mtime_cache=mtime_cache)
        assert snap3[rel_path][0] != hash1

    def test_compute_delta(self) -> None:
        ledger = da.ProvenanceLedger()

        before = {
            "stay_same.txt": ("hash1", 100.0),
            "will_modify.txt": ("hash2_old", 100.0),
            "will_delete.txt": ("hash3", 100.0),
        }
        after = {
            "stay_same.txt": ("hash1", 100.0),
            "will_modify.txt": ("hash2_new", 105.0),
            "created.txt": ("hash4", 105.0),
        }

        deltas = ledger.compute_delta(before, after)
        deltas_by_path = {d["path"]: d["type"] for d in deltas}

        assert deltas_by_path["will_modify.txt"] == "MODIFY"
        assert deltas_by_path["will_delete.txt"] == "DELETE"
        assert deltas_by_path["created.txt"] == "CREATED"
        assert "stay_same.txt" not in deltas_by_path

    def test_detect_blind_overwrites_tier_1_action(self, tmp_path: Path) -> None:
        ledger = da.ProvenanceLedger()

        created_file = tmp_path / "rogue.txt"
        created_file.write_text("unauthorized", encoding="utf-8")

        modified_file = tmp_path / "modified.py"
        modified_file.write_text("mutated", encoding="utf-8")

        allowed_file = tmp_path / "allowed.py"
        allowed_file.write_text("allowed mutation", encoding="utf-8")

        deltas = [
            {"type": "CREATED", "path": "rogue.txt"},
            {"type": "MODIFY", "path": "modified.py"},
            {"type": "MODIFY", "path": "allowed.py"},
        ]

        with patch.object(da, "safe_git_checkout") as mock_git_checkout:
            mutations = ledger.detect_blind_overwrites(
                deltas=deltas,
                tier=da.WorkspaceTier.TIER_1_IN_PLACE,
                allowed_paths={"allowed.py"},
                repo_root=tmp_path,
            )

            # Unauthorized created file must be unlinked
            assert not created_file.exists()
            # Unauthorized modified file must trigger git checkout restore
            mock_git_checkout.assert_called_once_with(tmp_path, "modified.py")

            mutated_paths = [m["path"] for m in mutations]
            assert "rogue.txt" in mutated_paths
            assert "modified.py" in mutated_paths
            assert "allowed.py" not in mutated_paths

    def test_append_to_ledger(self, tmp_path: Path) -> None:
        ledger = da.ProvenanceLedger()
        records = [
            da.ProvenanceRecord(
                session_id="sess_prov_1",
                tier="tier_1_in_place",
                timestamp="2026-03-30T12:00:00Z",
                event_type="audit_start",
                details={"target": "src/main.py"},
            ),
            da.ProvenanceRecord(
                session_id="sess_prov_1",
                tier="tier_1_in_place",
                timestamp="2026-03-30T12:00:05Z",
                event_type="audit_finish",
                details={"status": "success"},
            ),
        ]

        ledger.append_to_ledger(tmp_path, records)
        log_file = tmp_path / ".agy_provenance.jsonl"
        assert log_file.exists()

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        entry1 = json.loads(lines[0])
        assert entry1["session_id"] == "sess_prov_1"
        assert entry1["event_type"] == "audit_start"


# ==============================================================================
# 3. DynamicWorkspaceResolver Tests
# ==============================================================================


class TestDynamicWorkspaceResolver:
    """Tests for workspace provisioning, sandboxing, worktrees, and sweeping."""

    def test_evaluate_tier_matrix(self, tmp_path: Path) -> None:
        resolver = da.DynamicWorkspaceResolver(repo_root=tmp_path, auto_sweep=False)

        assert (
            resolver.evaluate_tier(da.AuditCategory.STATIC_AUDIT)
            == da.WorkspaceTier.TIER_1_IN_PLACE
        )
        assert (
            resolver.evaluate_tier(da.AuditCategory.DB_CONCURRENCY)
            == da.WorkspaceTier.TIER_2_SCRATCH_SANDBOX
        )
        assert (
            resolver.evaluate_tier(da.AuditCategory.REFACTOR_EVAL)
            == da.WorkspaceTier.TIER_3_SHADOW_WORKTREE
        )

        # read_only flag forces Tier 1
        assert (
            resolver.evaluate_tier(da.AuditCategory.DB_CONCURRENCY, read_only=True)
            == da.WorkspaceTier.TIER_1_IN_PLACE
        )

        # tier_override takes precedence
        assert (
            resolver.evaluate_tier(
                da.AuditCategory.STATIC_AUDIT,
                tier_override=da.WorkspaceTier.TIER_2_SCRATCH_SANDBOX,
            )
            == da.WorkspaceTier.TIER_2_SCRATCH_SANDBOX
        )

    def test_tier_2_provision_and_teardown(self, tmp_path: Path) -> None:
        resolver = da.DynamicWorkspaceResolver(repo_root=tmp_path, auto_sweep=False)

        # Success case: sandbox is purged cleanly
        ctx_ok = resolver.provision_workspace(
            tier=da.WorkspaceTier.TIER_2_SCRATCH_SANDBOX, session_id="s_success"
        )
        assert ctx_ok.workspace_path.exists()
        assert "dsh_sandbox_s_success" in ctx_ok.workspace_path.name
        (ctx_ok.workspace_path / "temp.txt").write_text("data", encoding="utf-8")

        summary_ok = resolver.teardown_workspace(ctx_ok, success=True)
        assert summary_ok.purged is True
        assert not ctx_ok.workspace_path.exists()

        # Failure case: failure evidence written, sandbox retained
        ctx_fail = resolver.provision_workspace(
            tier=da.WorkspaceTier.TIER_2_SCRATCH_SANDBOX, session_id="s_fail"
        )
        assert ctx_fail.workspace_path.exists()

        summary_fail = resolver.teardown_workspace(ctx_fail, success=False)
        assert summary_fail.purged is False
        assert ctx_fail.workspace_path.exists()
        evidence_file = ctx_fail.workspace_path / ".audit_failure_evidence"
        assert evidence_file.exists()
        assert summary_fail.evidence_path == ctx_fail.workspace_path

    def test_purge_directory_robust_removes_read_only_files(self, tmp_path: Path) -> None:
        resolver = da.DynamicWorkspaceResolver(repo_root=tmp_path, auto_sweep=False)
        target_dir = tmp_path / "locked_dir"
        target_dir.mkdir()
        ro_file = target_dir / "read_only.txt"
        ro_file.write_text("protected content", encoding="utf-8")

        # Mark read-only
        ro_file.chmod(stat.S_IREAD)

        success = resolver.purge_directory_robust(target_dir)
        assert success is True
        assert not target_dir.exists()

    def test_sweep_deferred_cleanups(self, tmp_path: Path) -> None:
        resolver = da.DynamicWorkspaceResolver(repo_root=tmp_path, auto_sweep=False)
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        # 1. Deferred cleanups file with a dead PID and alive PID
        dead_sandbox = scratch_dir / "dsh_sandbox_dead"
        dead_sandbox.mkdir()
        alive_sandbox = scratch_dir / "dsh_sandbox_alive"
        alive_sandbox.mkdir()

        deferred_file = scratch_dir / ".deferred_cleanups.txt"
        now_iso = datetime.now(timezone.utc).isoformat()
        deferred_file.write_text(
            f"{dead_sandbox}|111111|dead_sess|{now_iso}\n"
            f"{alive_sandbox}|222222|alive_sess|{now_iso}\n",
            encoding="utf-8",
        )

        # 2. Orphan sandbox (>24h old) without evidence -> should be purged
        orphan_old_no_ev = scratch_dir / "dsh_sandbox_old_orphan"
        orphan_old_no_ev.mkdir()
        old_mtime = time.time() - 90000.0  # > 24 hours
        os.utime(orphan_old_no_ev, (old_mtime, old_mtime))

        # 3. Orphan sandbox (>24h old) with evidence -> should be retained
        orphan_old_with_ev = scratch_dir / "dsh_sandbox_old_evidence"
        orphan_old_with_ev.mkdir()
        (orphan_old_with_ev / ".audit_failure_evidence").write_text("{}", encoding="utf-8")
        os.utime(orphan_old_with_ev, (old_mtime, old_mtime))

        def mock_alive(pid: int) -> bool:
            return pid == 222222

        with patch.object(da, "is_process_alive", side_effect=mock_alive):
            report = resolver.sweep_deferred_cleanups()

        assert not dead_sandbox.exists()
        assert alive_sandbox.exists()
        assert not orphan_old_no_ev.exists()
        assert orphan_old_with_ev.exists()
        assert report.entries_purged >= 1
        assert report.orphans_purged >= 1
        assert report.retained_failures >= 1

    def test_tier_3_git_worktree_and_patch_generation(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Tester"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "tester@example.com"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        tracked_file = repo_dir / "target.py"
        tracked_file.write_text("def hello(): pass\n", encoding="utf-8")
        subprocess.run(["git", "add", "target.py"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        resolver = da.DynamicWorkspaceResolver(repo_root=repo_dir, auto_sweep=False)
        ctx = resolver.provision_workspace(
            tier=da.WorkspaceTier.TIER_3_SHADOW_WORKTREE, session_id="wt_session"
        )

        assert ctx.workspace_path.exists()
        worktree_target = ctx.workspace_path / "target.py"
        assert worktree_target.exists()

        # Mutate tracked file in worktree
        worktree_target.write_text("def hello(): return 42\n", encoding="utf-8")

        summary = resolver.teardown_workspace(ctx, success=True)
        assert summary.patch_path is not None
        assert summary.patch_path.exists()
        patch_content = summary.patch_path.read_text(encoding="utf-8")
        assert "+def hello(): return 42" in patch_content
        assert not ctx.workspace_path.exists()


# ==============================================================================
# 4. ContextInjector & SessionManager Tests
# ==============================================================================


class TestContextAndSessionManager:
    """Tests for prompt injection, secret sanitization, and session state persistence."""

    def test_context_injector_redacts_secrets_and_builds_prompt(self, tmp_path: Path) -> None:
        task = da.AuditTask(
            category=da.AuditCategory.STATIC_AUDIT,
            task_prompt="Audit API using secret key sk-1234567890abcdef1234567890abcdef here",
        )
        ctx = da.WorkspaceContext(
            tier=da.WorkspaceTier.TIER_1_IN_PLACE,
            workspace_path=tmp_path,
            repo_root=tmp_path,
            session_id="sess_injector",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        prompt = da.ContextInjector.build_injected_prompt(
            task=task,
            context=ctx,
            session_state=None,
            recent_agy_files=["src/auth.py"],
        )

        assert str(tmp_path) in prompt
        assert "tier_1_in_place" in prompt
        assert "src/auth.py" in prompt
        assert "sk-1234567890abcdef1234567890abcdef" not in prompt
        assert "[REDACTED_OPENAI_KEY]" in prompt

    def test_session_manager_persistence(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        sm1 = da.SessionManager(scratch_dir=scratch_dir)
        session_id = "persistent_sess"
        state1, is_resumed = sm1.get_or_create_session(
            session_id=session_id, tier=da.WorkspaceTier.TIER_1_IN_PLACE
        )
        assert is_resumed is False
        assert state1.turn_count == 0

        sm1.record_turn(
            session_id=session_id,
            token_usage={"total": 200, "input": 150, "output": 50, "cache_read": 0},
        )

        # Reload manager pointing at same scratch_dir
        sm2 = da.SessionManager(scratch_dir=scratch_dir)
        state2, is_resumed2 = sm2.get_or_create_session(
            session_id=session_id, tier=da.WorkspaceTier.TIER_1_IN_PLACE
        )
        assert is_resumed2 is True
        assert state2.turn_count == 1
        assert state2.cumulative_tokens["total"] == 200


# ==============================================================================
# 5. NDJSONStreamParser Tests
# ==============================================================================


class TestNDJSONStreamParser:
    """Tests for NDJSON streaming output parsing, metrics, and error detection."""

    def test_parser_event_lifecycle(self) -> None:
        parser = da.NDJSONStreamParser()

        # 1. Session init event
        parser.feed_line(
            json.dumps(
                {
                    "type": "session",
                    "sessionId": "ndjson_sess_1",
                }
            )
        )
        assert parser.session_id == "ndjson_sess_1"

        # 2. Tool call event
        parser.feed_line(
            json.dumps(
                {
                    "type": "tool_call",
                    "callId": "c1",
                    "tool": "bash",
                    "input": {"command": "ls"},
                }
            )
        )
        assert len(parser.tool_calls) == 1
        assert parser.tool_calls["c1"].tool_name == "bash"

        # 3. Tool result event
        parser.feed_line(
            json.dumps(
                {
                    "type": "tool_result",
                    "callId": "c1",
                    "status": "completed",
                    "result": "file1.py\nfile2.py",
                }
            )
        )
        assert parser.tool_calls["c1"].status == "completed"

        # 4. Text & final chunk
        parser.feed_line(
            json.dumps(
                {
                    "type": "text",
                    "text": "Everything is normal.",
                }
            )
        )
        assert "Everything is normal." in parser.text_chunks

        # 5. Status usage & cache hit calculation (80/100 => 80.0%)
        parser.feed_line(
            json.dumps(
                {
                    "type": "status",
                    "usage": {
                        "totalTokens": 100,
                        "inputTokens": 20,
                        "outputTokens": 0,
                        "cacheReadTokens": 80,
                    },
                }
            )
        )
        assert parser.last_usage is not None
        assert parser.cache_hit_rate == pytest.approx(80.0)

        # 6. Malformed JSON lines should not crash parser
        parser.feed_line("{malformed_json: bad")

        # 7. Unknown session event
        parser.feed_line(
            json.dumps(
                {
                    "type": "error",
                    "message": "Session ndjson_sess_1 does not exist",
                }
            )
        )
        assert parser.unknown_session_detected is True
        assert "does not exist" in parser.error_message


# ==============================================================================
# 6. execute_streaming_subprocess & DSHAuditorClient Tests
# ==============================================================================


class TestSubprocessAndClient:
    """Tests for streaming subprocess execution watchdog and DSHAuditorClient."""

    def test_subprocess_timeout_watchdog_kills_child(self, tmp_path: Path) -> None:
        parser = da.NDJSONStreamParser()
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]

        start_t = time.time()
        exit_code, _, _, _, timed_out = da.execute_streaming_subprocess(
            cmd_args=cmd,
            injected_prompt="test",
            cwd=tmp_path,
            timeout_sec=0.35,
            parser=parser,
        )
        elapsed = time.time() - start_t

        assert timed_out is True
        assert elapsed < 3.0  # Clean abort well before the 10s sleep
