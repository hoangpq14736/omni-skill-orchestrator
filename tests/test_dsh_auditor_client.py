import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.dsh_auditor import (
    AuditCategory,
    AuditTask,
    DSHAuditorClient,
    DSHBinaryNotFoundError,
    WorkspaceTier,
)


@pytest.fixture
def repo_path(tmp_path):
    """Create a temporary repo directory (git init not required)."""
    (tmp_path / "some_file.txt").write_text("initial")
    return tmp_path


def _mock_resolve_binary(*_):
    """Return a dummy path for the dsh binary."""
    return "dsh"


def _make_parser_setter(session_id="sess123", final_text="ok", unknown=False):
    """Factory returning a side-effect that feeds realistic NDJSON events to parser."""
    def setter(cmd_args, injected_prompt, cwd, timeout_sec, parser, env=None):
        lines = [
            json.dumps({"type": "session", "sessionId": session_id}),
            json.dumps({"type": "status", "usage": {"totalTokens": 2, "inputTokens": 1, "outputTokens": 1, "cacheReadTokens": 0}}),
            json.dumps({"type": "final", "sessionId": session_id, "text": final_text}),
        ]
        if unknown:
            lines.append(json.dumps({"type": "error", "message": f"Session {session_id} does not exist"}))
        for ln in lines:
            parser.feed_line(ln)
        return (1 if unknown else 0), lines, [], 9999, False
    return setter


def test_tier1_read_only_success_and_lock_released(repo_path):
    """Tier-1 read-only audit should succeed and leave no lockfile."""
    client = DSHAuditorClient(repo_root=repo_path, auto_sweep=False)

    task = AuditTask(
        category=AuditCategory.STATIC_AUDIT,
        task_prompt="Check something",
        tier_override=WorkspaceTier.TIER_1_IN_PLACE,
        read_only=True,
    )

    with patch(
        "scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary
    ), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess",
        side_effect=_make_parser_setter(),
    ):
        result = client.execute_audit(task)

    assert result.success is True
    assert result.sanitized_output == "ok"
    assert '"type": "final"' in result.raw_output

    lockfile = repo_path / ".dsh_audit.lock"
    assert not lockfile.exists()


def test_tier1_unauthorized_mutation_rollback(repo_path):
    """Unauthorized file creation during Tier-1 audit should be rolled back."""
    client = DSHAuditorClient(repo_root=repo_path, auto_sweep=False)

    unexpected = repo_path / "unexpected.txt"

    def fake_execute(cmd_args, injected_prompt, cwd, timeout_sec, parser, env=None):
        parser.feed_line(json.dumps({"type": "session", "sessionId": "sess123"}))
        parser.feed_line(json.dumps({"type": "final", "sessionId": "sess123", "text": "done"}))
        unexpected.write_text("malicious")
        return 0, [], [], 1111, False

    task = AuditTask(
        category=AuditCategory.STATIC_AUDIT,
        task_prompt="Audit repo",
        tier_override=WorkspaceTier.TIER_1_IN_PLACE,
        read_only=True,
        target_paths=[],
    )

    with patch(
        "scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary
    ), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess",
        side_effect=fake_execute,
    ):
        result = client.execute_audit(task)

    assert result.unauthorized_mutations
    assert any(unexpected.name in str(u) for u in result.unauthorized_mutations)
    assert not unexpected.exists()


def test_ec013_stale_session_retries_without_session_id(repo_path):
    """Stale session error should trigger a retry without the session flag."""
    client = DSHAuditorClient(repo_root=repo_path, auto_sweep=False)
    captured = []

    def first_call(cmd_args, injected_prompt, cwd, timeout_sec, parser, env=None):
        captured.append(list(cmd_args))
        parser.feed_line(json.dumps({"type": "error", "message": "Session stale_123 does not exist"}))
        return 1, [], [], 2222, False

    def second_call(cmd_args, injected_prompt, cwd, timeout_sec, parser, env=None):
        captured.append(list(cmd_args))
        parser.feed_line(json.dumps({"type": "session", "sessionId": "new"}))
        parser.feed_line(json.dumps({"type": "status", "usage": {"totalTokens": 5, "inputTokens": 2, "outputTokens": 3, "cacheReadTokens": 0}}))
        parser.feed_line(json.dumps({"type": "final", "sessionId": "new", "text": "audit succeeded"}))
        return 0, [], [], 3333, False

    task = AuditTask(
        category=AuditCategory.STATIC_AUDIT,
        task_prompt="Run audit",
        session_id="stale_123",
        tier_override=WorkspaceTier.TIER_1_IN_PLACE,
    )

    calls = iter([first_call, second_call])

    def dispatch(*args, **kwargs):
        return next(calls)(*args, **kwargs)

    with patch(
        "scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary
    ), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess",
        side_effect=dispatch,
    ):
        result = client.execute_audit(task)

    assert len(captured) == 2
    assert any("--session-id" in arg for arg in captured[0])
    assert not any("--session-id" in arg for arg in captured[1])
    assert result.success is True
    assert result.session_id == "new"
    assert result.sanitized_output == "audit succeeded"


def test_ec015_missing_dsh_binary_fails_soft(repo_path):
    """Missing dsh binary should produce a graceful failure."""
    client = DSHAuditorClient(repo_root=repo_path, auto_sweep=False)

    task = AuditTask(
        category=AuditCategory.STATIC_AUDIT,
        task_prompt="Anything",
        tier_override=WorkspaceTier.TIER_1_IN_PLACE,
    )

    with patch(
        "scripts.dsh_auditor.resolve_dsh_binary",
        side_effect=DSHBinaryNotFoundError("dsh binary not found"),
    ), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess"
    ) as mock_exec:
        result = client.execute_audit(task)
        mock_exec.assert_not_called()

    assert result.success is False
    assert result.error_message
    assert "dsh" in result.error_message.lower() or "binary" in result.error_message.lower()


def test_dead_pid_lock_reclaimed_immediately_within_timeout(repo_path):
    """Finding 1: Dead PID holding a fresh (<1s) lock must be reclaimed immediately."""
    from datetime import datetime, timezone
    from scripts.dsh_auditor import LockManager

    mgr = LockManager(repo_root=repo_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    mgr.lock_path.write_text(
        json.dumps(
            {
                "session_id": "crashed_sess",
                "scope": "tier_1_in_place",
                "pid": 999998,
                "hostname": "test-host",
                "acquired_at": now_iso,
                "heartbeat_at": now_iso,
                "timeout_sec": 120.0,
                "nonce": "dead_fresh_nonce",
            }
        ),
        encoding="utf-8",
    )
    with patch("scripts.dsh_auditor.is_process_alive", return_value=False):
        assert mgr.acquire("recovered_sess", retry_deadline_sec=0.3) is True
    mgr.release()


def test_execute_audit_handles_lock_contention_fails_soft(repo_path):
    """Finding 2: execute_audit returns fail-soft AuditResult on LockContentionError."""
    from scripts.dsh_auditor import LockContentionError

    client = DSHAuditorClient(repo_root=repo_path, auto_sweep=False)
    task = AuditTask(category=AuditCategory.STATIC_AUDIT, task_prompt="Check lock", read_only=True)
    with patch.object(client.lock_manager, "acquire", side_effect=LockContentionError("busy")):
        result = client.execute_audit(task)

    assert result.success is False
    assert result.error_message == "LOCK_CONTENTION_TIMEOUT"


def test_tier2_blocks_unapproved_repo_root_mutation(repo_path):
    """Finding 4: Tier 2 rolls back unauthorized edits to mounted repo_root files."""
    client = DSHAuditorClient(repo_root=repo_path, auto_sweep=False)
    stray = repo_path / "stray_repo_edit.py"

    def fake_tier2(cmd_args, injected_prompt, cwd, timeout_sec, parser, env=None):
        parser.feed_line(json.dumps({"type": "session", "sessionId": "t2_sess"}))
        parser.feed_line(json.dumps({"type": "final", "sessionId": "t2_sess", "text": "done"}))
        stray.write_text("oops")
        return 0, [], [], 4444, False

    task = AuditTask(category=AuditCategory.DB_CONCURRENCY, task_prompt="Test WAL")
    with patch("scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess", side_effect=fake_tier2
    ):
        result = client.execute_audit(task)

    assert result.tier == WorkspaceTier.TIER_2_SCRATCH_SANDBOX
    assert result.success is False
    assert result.unauthorized_mutations
    assert not stray.exists()


def test_cli_accepts_uppercase_category_and_null_usage(repo_path):
    """Finding 6 & Gatekeeper: main() handles uppercase --category and null usage counts."""
    from scripts.dsh_auditor import NDJSONStreamParser, main

    p = NDJSONStreamParser()
    p.feed_line(json.dumps({"type": "status", "usage": {"totalTokens": None, "cacheReadTokens": "bad"}}))
    assert p.last_usage == {"total": 0, "input": 0, "output": 0, "cache_read": 0}

    with patch(
        "sys.argv",
        ["dsh_auditor.py", "--task", "hi", "--category", "STATIC_AUDIT", "--cwd", str(repo_path), "--json"],
    ), patch("scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess",
        side_effect=_make_parser_setter(final_text="cli ok"),
    ):
        rc = main()
    assert rc == 0


def test_spec_dataclass_aliases_compatibility(repo_path):
    """Finding 5: Spec field aliases work without breaking existing attributes."""
    client = DSHAuditorClient(repo_root=repo_path, auto_sweep=False)
    task = AuditTask(
        category=AuditCategory.STATIC_AUDIT,
        task_prompt="Alias check",
        read_only=True,
        task_id="task-spec-99",
    )
    assert task.prompt == "Alias check"

    with patch("scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess",
        side_effect=_make_parser_setter(final_text="verified"),
    ):
        result = client.execute_audit(task)

    assert result.task_id == "task-spec-99"
    assert result.workspace_tier == result.tier
    assert result.verdict_text == result.sanitized_output == "verified"
    assert result.total_tokens == 2
    assert result.diff_patch_path is None
    assert result.sandbox_evidence_path is None
    assert result.error is None


def test_cli_target_paths_does_not_swallow_positional_prompt_and_emits_spec_json(repo_path, capsys):
    """CLI --target-paths must not swallow positional prompt and --json includes spec keys."""
    from scripts.dsh_auditor import main

    with patch(
        "sys.argv",
        [
            "dsh_auditor.py",
            "--target-paths",
            "some_file.txt,other.py",
            "--category",
            "STATIC_AUDIT",
            "--cwd",
            str(repo_path),
            "--json",
            "positional audit prompt",
        ],
    ), patch("scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess",
        side_effect=_make_parser_setter(final_text="json ok"),
    ):
        rc = main()

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["task_id"]
    assert out["workspace_tier"] == "tier_1_in_place"
    assert out["verdict_text"] == "json ok"
    assert "final_text" not in out
    assert out["total_tokens"] == 2


def test_tier3_worktree_syncs_uncommitted_agy_edits_without_polluting_patch(tmp_path):
    """Tier 3 worktree sees Agy's uncommitted/untracked files, while patch captures only DSH's delta."""
    import subprocess
    from scripts.dsh_auditor import DynamicWorkspaceResolver

    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(tmp_path), check=True)
    (tmp_path / "app.py").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL)

    # Agy's uncommitted modification + untracked file
    (tmp_path / "app.py").write_text("v2-agy\n", encoding="utf-8")
    (tmp_path / "agy_draft.py").write_text("draft = 1\n", encoding="utf-8")

    dwr = DynamicWorkspaceResolver(tmp_path, auto_sweep=False)
    ctx = dwr.provision_workspace(WorkspaceTier.TIER_3_SHADOW_WORKTREE, "t3_sync")

    assert (ctx.workspace_path / "app.py").read_text(encoding="utf-8") == "v2-agy\n"
    assert (ctx.workspace_path / "agy_draft.py").read_text(encoding="utf-8") == "draft = 1\n"

    # DSH edits only agy_draft.py inside worktree
    (ctx.workspace_path / "agy_draft.py").write_text("draft = 2\n", encoding="utf-8")
    summary = dwr.teardown_workspace(ctx, success=True)

    assert summary.patch_path and summary.patch_path.exists()
    patch_content = summary.patch_path.read_text(encoding="utf-8")
    assert "+draft = 2" in patch_content
    assert "v2-agy" not in patch_content


def test_tier1_rollback_preserves_dirty_tracked_and_untracked_agy_files(tmp_path):
    """Dirty rollback must restore Agy's uncommitted and untracked content instead of reverting to HEAD."""
    import subprocess

    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(tmp_path), check=True)
    tracked = tmp_path / "tracked.py"
    tracked.write_text("head-version\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL)

    # Agy's uncommitted dirty edit + new untracked file
    tracked.write_text("agy-uncommitted-wip\n", encoding="utf-8")
    untracked = tmp_path / "agy_new.py"
    untracked.write_text("agy-new-work\n", encoding="utf-8")

    client = DSHAuditorClient(repo_root=tmp_path, auto_sweep=False)

    def rogue_dsh(cmd_args, injected_prompt, cwd, timeout_sec, parser, env=None):
        parser.feed_line(json.dumps({"type": "session", "sessionId": "rogue_1"}))
        parser.feed_line(json.dumps({"type": "final", "sessionId": "rogue_1", "text": "tampered"}))
        tracked.write_text("dsh-corrupted\n", encoding="utf-8")
        untracked.unlink()
        return 0, [], [], 7777, False

    task = AuditTask(category=AuditCategory.STATIC_AUDIT, task_prompt="Audit", read_only=True)
    with patch("scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess", side_effect=rogue_dsh
    ):
        result = client.execute_audit(task)

    assert result.success is False
    assert len(result.unauthorized_mutations) == 2
    assert tracked.read_text(encoding="utf-8") == "agy-uncommitted-wip\n"
    assert untracked.read_text(encoding="utf-8") == "agy-new-work\n"


def test_missing_dsh_binary_fails_fast_before_lock_or_tier3_worktree(repo_path):
    """Missing DSH on a new machine must fail fast without acquiring lock or creating Tier 3 worktrees."""
    client = DSHAuditorClient(repo_root=repo_path, auto_sweep=False)
    task = AuditTask(
        category=AuditCategory.REFACTOR_EVAL,
        task_prompt="Evaluate refactor",
    )

    with patch(
        "scripts.dsh_auditor.resolve_dsh_binary",
        side_effect=DSHBinaryNotFoundError("dsh binary not found"),
    ), patch.object(client.dwr, "provision_workspace") as mock_prov:
        result = client.execute_audit(task)
        mock_prov.assert_not_called()

    assert result.success is False
    assert result.exit_code == -1
    assert not (repo_path / ".dsh_audit.lock").exists()


def test_read_only_enforces_empty_allowed_paths_even_when_target_paths_provided(tmp_path):
    """--read-only + --target-paths must treat target_paths as inspection scope only and roll back writes."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(tmp_path), check=True)
    target = tmp_path / "app.py"
    original = "def ok():\n    return 1\n"
    target.write_text(original, encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL)

    client = DSHAuditorClient(repo_root=tmp_path, auto_sweep=False)
    captured_prompt = []

    def sneaky_dsh(cmd_args, injected_prompt, cwd, timeout_sec, parser, env=None):
        captured_prompt.append(injected_prompt)
        parser.feed_line(json.dumps({"type": "session", "sessionId": "ro_1"}))
        parser.feed_line(json.dumps({"type": "final", "sessionId": "ro_1", "text": "edited anyway"}))
        target.write_text("# overwritten despite read-only\n", encoding="utf-8")
        return 0, [], [], 8888, False

    task = AuditTask(
        category=AuditCategory.STATIC_AUDIT,
        task_prompt="Inspect app.py only",
        read_only=True,
        target_paths=["app.py"],
    )

    with patch("scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess", side_effect=sneaky_dsh
    ):
        result = client.execute_audit(task)

    assert "NO writes allowed" in captured_prompt[0]
    assert result.success is False
    assert result.error_message == "VIOLATION_TIER1_UNAUTHORIZED_MUTATION"
    assert len(result.unauthorized_mutations) == 1
    assert target.read_text(encoding="utf-8") == original


def test_execute_audit_unexpected_exception_runs_finally_teardown_and_unlock(tmp_path):
    """Unexpected failure after provisioning must still run emergency teardown, purge backups, and release lock."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(tmp_path), check=True)
    tracked = tmp_path / "base.py"
    tracked.write_text("base = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.py"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL)

    client = DSHAuditorClient(repo_root=tmp_path, auto_sweep=False)
    (tmp_path / "dirty.py").write_text("wip\n", encoding="utf-8")
    provisioned = []
    orig_provision = client.dwr.provision_workspace

    def capture_provision(tier, session_id):
        ctx = orig_provision(tier, session_id)
        provisioned.append(ctx)
        return ctx

    def fake_exec(cmd_args, injected_prompt, cwd, timeout_sec, parser, env=None):
        parser.feed_line(json.dumps({"type": "session", "sessionId": "boom_1"}))
        parser.feed_line(json.dumps({"type": "final", "sessionId": "boom_1", "text": "ok"}))
        return 0, [], [], None, False

    task = AuditTask(category=AuditCategory.DB_CONCURRENCY, task_prompt="Test WAL")

    with patch("scripts.dsh_auditor.resolve_dsh_binary", _mock_resolve_binary), patch.object(
        client.dwr, "provision_workspace", side_effect=capture_provision
    ), patch(
        "scripts.dsh_auditor.execute_streaming_subprocess", side_effect=fake_exec
    ), patch(
        "scripts.dsh_auditor.ProvenanceLedger.append_to_ledger",
        side_effect=OSError("disk full"),
    ):
        try:
            client.execute_audit(task)
            assert False, "Expected OSError to propagate"
        except OSError:
            pass

    assert len(provisioned) == 1
    sandbox_dir = provisioned[0].workspace_path
    assert (sandbox_dir / ".audit_failure_evidence").exists()
    assert not (tmp_path / ".dsh_audit.lock").exists()
    assert not (client.dwr.scratch_dir / "rollback_backups").exists()


def test_tier3_locked_worktree_registers_deferred_cleanup(repo_path):
    """When Tier 3 shadow worktree cannot be purged on Windows, it should register in .deferred_cleanups."""
    from scripts.dsh_auditor import DynamicWorkspaceResolver, WorkspaceContext

    dwr = DynamicWorkspaceResolver(repo_root=repo_path, auto_sweep=False)
    wt_dir = dwr.scratch_dir / "shadow_worktrees" / "dsh_shadow_locked"
    wt_dir.mkdir(parents=True, exist_ok=True)
    ctx = WorkspaceContext(
        tier=WorkspaceTier.TIER_3_SHADOW_WORKTREE,
        workspace_path=wt_dir,
        repo_root=repo_path,
        session_id="locked_wt",
        shadow_branch="deadbeef",
    )

    with patch.object(dwr, "purge_directory_robust", return_value=False), patch(
        "scripts.dsh_auditor.subprocess.run", side_effect=subprocess.SubprocessError("locked")
    ):
        summary = dwr.teardown_workspace(ctx, success=True, child_pid=4242)

    assert summary.purged is False
    assert summary.deferred is True
    assert dwr._deferred_file.exists()
    assert "dsh_shadow_locked|4242|locked_wt|" in dwr._deferred_file.read_text(encoding="utf-8")





