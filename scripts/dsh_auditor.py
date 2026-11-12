#!/usr/bin/env python3
"""Empirical audit orchestrator for DeepSeek Harness (DSH).

Zero-trust, multi-tier isolation, provenance tracking, and resilient execution
engine adhering strictly to specs/004-dsh-empirical-auditor/spec.md.
100% Python 3.11+ Standard Library.
"""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

# Reconfigure stdout/stderr to UTF-8 on Windows environments
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Graceful import of credential sanitizer with fallback regex
try:
    from scripts.sanitizer import redact_credentials
except ImportError:
    try:
        from sanitizer import redact_credentials  # type: ignore
    except ImportError:
        _CRED_PATTERN = re.compile(
            r"(?i)\b(bearer\s+[a-z0-9_\-\.]{16,}|(?:api[_-]?key|secret|password|auth[_-]?token)"
            r"\s*[:=]\s*['\"]?[a-z0-9_\-\.]{8,}['\"]?)"
        )

        def redact_credentials(text: Optional[str]) -> str:
            """Fallback credential redaction regex."""
            if not text:
                return ""
            return _CRED_PATTERN.sub("[REDACTED_SECRET]", text)


# -----------------------------------------------------------------------------
# Enums and Domain Data Models
# -----------------------------------------------------------------------------

class WorkspaceTier(str, Enum):
    TIER_1_IN_PLACE = "tier_1_in_place"
    TIER_2_SCRATCH_SANDBOX = "tier_2_scratch_sandbox"
    TIER_3_SHADOW_WORKTREE = "tier_3_shadow_worktree"


class AuditCategory(str, Enum):
    STATIC_AUDIT = "static_audit"
    TEST_EXISTING = "test_existing"
    BUG_REPRODUCE = "bug_reproduce"
    DB_CONCURRENCY = "db_concurrency"
    ISOLATED_PROBE = "isolated_probe"
    REFACTOR_EVAL = "refactor_eval"
    SPECULATIVE_FIX = "speculative_fix"
    STRESS_TEST = "stress_test"


class LockContentionError(RuntimeError):
    """Raised when workspace lock acquisition times out or is held."""


class DSHBinaryNotFoundError(FileNotFoundError):
    """Raised when the dsh CLI binary cannot be discovered."""


@dataclass(frozen=True)
class LockPayload:
    session_id: str
    scope: str
    pid: int
    hostname: str
    acquired_at: str
    heartbeat_at: str
    timeout_sec: float
    nonce: str
    lock_version: str = "1.1"
    agent: str = "dsh"


@dataclass
class ToolCallRecord:
    call_id: str
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Optional[str] = None
    is_error: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def command_input(self) -> Dict[str, Any]:
        return self.arguments

    @property
    def result_output(self) -> Optional[str]:
        return self.result


@dataclass
class DSHRunEvent:
    event_type: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_line: str = ""


@dataclass
class WorkspaceContext:
    tier: WorkspaceTier
    workspace_path: Path
    repo_root: Path
    session_id: str
    shadow_branch: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class CleanupSummary:
    tier: WorkspaceTier
    workspace_path: Path
    purged: bool
    evidence_path: Optional[Path] = None
    patch_path: Optional[Path] = None
    deferred: bool = False
    details: str = ""


@dataclass
class SweepReport:
    entries_processed: int = 0
    entries_purged: int = 0
    entries_deferred: int = 0
    orphans_purged: int = 0
    retained_failures: int = 0
    killed_zombies: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class ProvenanceRecord:
    session_id: str
    tier: str
    timestamp: str
    event_type: str  # PRE_SNAPSHOT, POST_SNAPSHOT, ROLLBACK, MUTATION, PURGE, STALE_LOCK_PURGE
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditTask:
    category: AuditCategory
    task_prompt: str
    session_id: Optional[str] = None
    target_paths: List[str] = field(default_factory=list)
    tier_override: Optional[WorkspaceTier] = None
    read_only: bool = False
    timeout_sec: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def prompt(self) -> str:
        return self.task_prompt


@dataclass
class AuditResult:
    session_id: str
    category: AuditCategory
    tier: WorkspaceTier
    success: bool
    exit_code: int
    raw_output: str
    sanitized_output: str
    tool_calls: List[ToolCallRecord]
    token_usage: Dict[str, int]
    cache_hit_rate: float
    duration_sec: float
    workspace_path: str
    evidence_path: Optional[str] = None
    patch_path: Optional[str] = None
    unauthorized_mutations: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    task_id: str = ""

    @property
    def workspace_tier(self) -> WorkspaceTier:
        return self.tier

    @property
    def verdict_text(self) -> str:
        return self.sanitized_output

    @property
    def diff_patch_path(self) -> Optional[str]:
        return self.patch_path

    @property
    def sandbox_evidence_path(self) -> Optional[str]:
        return self.evidence_path

    @property
    def error(self) -> Optional[str]:
        return self.error_message

    @property
    def total_tokens(self) -> int:
        return int(self.token_usage.get("total", 0))


@dataclass
class SessionState:
    session_id: str
    created_at: str
    last_turn_at: str
    turn_count: int
    tier: WorkspaceTier
    cumulative_tokens: Dict[str, int] = field(
        default_factory=lambda: {"total": 0, "input": 0, "output": 0, "cache_read": 0}
    )


# -----------------------------------------------------------------------------
# Binary Discovery & System Utilities
# -----------------------------------------------------------------------------

def normalize_path(path: Path | str) -> str:
    """Normalize filesystem paths consistently across Windows drive-letter casing."""
    return os.path.normcase(os.path.realpath(str(path)))


def find_repo_root(start_path: Optional[Path] = None) -> Path:
    """Traverse upwards to discover repository root marked by .git."""
    curr = (start_path or Path.cwd()).resolve()
    for parent in [curr, *curr.parents]:
        if (parent / ".git").exists():
            return parent
    return curr


def resolve_dsh_binary() -> str:
    """Discover the DSH executable across system path and standard Windows install locations."""
    env_override = os.environ.get("DSH_CLI_PATH")
    if env_override and Path(env_override).is_file():
        return str(Path(env_override).resolve())

    which_dsh = shutil.which("dsh") or shutil.which("dsh.cmd")
    if which_dsh:
        return str(Path(which_dsh).resolve())

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = (
            Path(local_app_data)
            / "Programs"
            / "DeepSeek Harness"
            / "resources"
            / "runtime"
            / "cli"
            / "bin"
            / "dsh.cmd"
        )
        if candidate.is_file():
            return str(candidate.resolve())

    raise DSHBinaryNotFoundError(
        "Could not locate 'dsh' executable. Ensure DeepSeek Harness is installed, "
        "present on PATH, or specified via DSH_CLI_PATH."
    )


def is_process_alive(pid: int) -> bool:
    """Check process liveness reliably on Windows (STILL_ACTIVE == 259) and POSIX."""
    if pid <= 0:
        return False
    if os.name == "nt":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            success = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            return bool(success and exit_code.value == 259)
        finally:
            kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


def terminate_process_tree(pid: int) -> None:
    """Forcibly terminate a process and all its child descendants."""
    if not is_process_alive(pid):
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


# -----------------------------------------------------------------------------
# Git Self-Healing Helpers
# -----------------------------------------------------------------------------

def resolve_git_dir(repo_root: Path) -> Path:
    """Locate the actual gitdir, supporting standard repos and worktrees."""
    dot_git = repo_root / ".git"
    if dot_git.is_file():
        try:
            content = dot_git.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                target = Path(content.split("gitdir:", 1)[1].strip())
                if not target.is_absolute():
                    target = (repo_root / target).resolve()
                return target
        except Exception:
            pass
    return dot_git


def ensure_git_index_unlocked(repo_root: Path) -> None:
    """Self-heal stale git index.lock files (>30s with no active git.exe)."""
    git_dir = resolve_git_dir(repo_root)
    lock_file = git_dir / "index.lock"
    if not lock_file.exists():
        return

    try:
        age_sec = time.time() - lock_file.stat().st_mtime
        if age_sec > 30.0:
            is_git_running = False
            if os.name == "nt":
                tl = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq git.exe", "/FO", "CSV"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                is_git_running = "git.exe" in tl.stdout.lower()

            if not is_git_running:
                lock_file.unlink(missing_ok=True)
                sys.stderr.write(
                    f"[WARN] Purged stale git index lock at {lock_file} (age={age_sec:.1f}s)\n"
                )
                ProvenanceLedger.append_to_ledger(
                    repo_root,
                    [
                        ProvenanceRecord(
                            session_id="system",
                            tier="git_self_heal",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            event_type="STALE_GIT_INDEX_LOCK_PURGED",
                            details={"path": str(lock_file), "age_sec": age_sec},
                        )
                    ],
                )
    except Exception as exc:
        sys.stderr.write(f"[WARN] Failed to evaluate git index lock: {exc}\n")


def safe_git_worktree_add(repo_root: Path, shadow_path: Path, ref: str = "HEAD") -> None:
    """Add a detached git worktree with index unlocking and jittered backoff."""
    delays = [0.2, 0.5, 1.0]
    last_err = ""
    for delay in delays:
        ensure_git_index_unlocked(repo_root)
        proc = subprocess.run(
            ["git", "worktree", "add", "--detach", str(shadow_path), ref],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return
        last_err = proc.stderr
        time.sleep(delay + random.uniform(0.01, 0.05))

    raise RuntimeError(
        f"Failed to create git worktree at {shadow_path} after retries: {last_err.strip()}"
    )


def safe_git_checkout(repo_root: Path, rel_path: str) -> bool:
    """Restore a tracked file from HEAD with retries and lock healing."""
    delays = [0.2, 0.5, 1.0]
    for delay in delays:
        ensure_git_index_unlocked(repo_root)
        proc = subprocess.run(
            ["git", "checkout", "HEAD", "--", rel_path],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return True
        time.sleep(delay + random.uniform(0.01, 0.04))
    return False


# -----------------------------------------------------------------------------
# MMPP Layer 1: Multi-Process Concurrency Lock (LockManager)
# -----------------------------------------------------------------------------

class LockManager:
    """Multi-process concurrency coordinator using Win32 MoveFileW atomic rename."""

    def __init__(self, repo_root: Path, lock_filename: str = ".dsh_audit.lock"):
        self.repo_root = repo_root.resolve()
        self.lock_path = self.repo_root / lock_filename
        self.held = False
        self.current_payload: Optional[LockPayload] = None
        self._stop_heartbeat = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None

    def acquire(
        self,
        session_id: str,
        scope: str = "tier_1_in_place",
        timeout_sec: float = 120.0,
        retry_deadline_sec: float = 10.0,
        base_backoff_sec: float = 0.05,
    ) -> bool:
        self.repo_root.mkdir(parents=True, exist_ok=True)
        nonce = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = LockPayload(
            session_id=session_id,
            scope=scope,
            pid=os.getpid(),
            hostname=(
                os.uname().nodename
                if hasattr(os, "uname")
                else os.environ.get("COMPUTERNAME", "unknown")
            ),
            acquired_at=now_iso,
            heartbeat_at=now_iso,
            timeout_sec=timeout_sec,
            nonce=nonce,
        )

        tmp_path = self.repo_root / f"{self.lock_path.name}.{nonce}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(asdict(payload), f)
                f.flush()
                os.fsync(f.fileno())

            start_t = time.time()
            attempt = 0
            while True:
                try:
                    # Atomic exclusive lock creation across both NTFS and POSIX
                    if sys.platform.startswith("win"):
                        os.rename(tmp_path, self.lock_path)
                    else:
                        os.link(tmp_path, self.lock_path)
                        tmp_path.unlink(missing_ok=True)
                    self.held = True
                    self.current_payload = payload
                    self._start_heartbeat(timeout_sec)
                    return True
                except (FileExistsError, PermissionError):
                    self._handle_existing_lock()

                if (time.time() - start_t) >= retry_deadline_sec:
                    break

                attempt += 1
                t_sleep = base_backoff_sec * (1.5 ** min(attempt, 5)) + random.uniform(
                    0.01, 0.03
                )
                time.sleep(t_sleep)

            raise LockContentionError(
                f"Failed to acquire workspace lock at {self.lock_path} within {retry_deadline_sec}s. "
                "Workspace is occupied by another audit session."
            )
        finally:
            if not self.held and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def _handle_existing_lock(self) -> None:
        if not self.lock_path.exists():
            return
        try:
            stat_res = self.lock_path.stat()
            if stat_res.st_size == 0:
                age_sec = time.time() - stat_res.st_mtime
                if age_sec > 5.0:
                    self.lock_path.unlink(missing_ok=True)
                    sys.stderr.write(
                        f"[WARN] Purged stale orphaned 0-byte lockfile: {self.lock_path} (age={age_sec:.2f}s)\n"
                    )
                return

            raw = self.lock_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            heartbeat_at = datetime.fromisoformat(str(data["heartbeat_at"]))
            if heartbeat_at.tzinfo is None:
                heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
            delta_sec = (datetime.now(timezone.utc) - heartbeat_at).total_seconds()
            timeout_sec = float(data.get("timeout_sec", 120.0))

            holder_pid = int(data.get("pid", -1))
            if not is_process_alive(holder_pid) or delta_sec > timeout_sec:
                self._attempt_stale_reclaim(data.get("nonce", ""))
        except (FileNotFoundError, PermissionError, json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass

    def _attempt_stale_reclaim(self, expected_nonce: str) -> bool:
        reclaim_path = self.repo_root / f"{self.lock_path.name}.{uuid.uuid4().hex}.reclaim"
        try:
            os.rename(self.lock_path, reclaim_path)
        except (FileNotFoundError, PermissionError):
            return False

        try:
            raw = reclaim_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if data.get("nonce") == expected_nonce:
                reclaim_path.unlink(missing_ok=True)
                sys.stderr.write(
                    f"[WARN] Reclaimed stale workspace lock held by dead PID {data.get('pid')}\n"
                )
                return True
            else:
                os.replace(reclaim_path, self.lock_path)
                return False
        except Exception:
            if reclaim_path.exists():
                try:
                    os.replace(reclaim_path, self.lock_path)
                except OSError:
                    pass
            return False

    def _start_heartbeat(self, timeout_sec: float) -> None:
        self._stop_heartbeat.clear()
        interval = min(max(timeout_sec / 4.0, 1.0), 5.0)

        def _loop() -> None:
            while not self._stop_heartbeat.wait(interval):
                if not self.held or not self.current_payload:
                    break
                try:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    updated = LockPayload(
                        session_id=self.current_payload.session_id,
                        scope=self.current_payload.scope,
                        pid=self.current_payload.pid,
                        hostname=self.current_payload.hostname,
                        acquired_at=self.current_payload.acquired_at,
                        heartbeat_at=now_iso,
                        timeout_sec=self.current_payload.timeout_sec,
                        nonce=self.current_payload.nonce,
                    )
                    tmp_hb = (
                        self.repo_root
                        / f"{self.lock_path.name}.{self.current_payload.nonce}.hb.tmp"
                    )
                    with open(tmp_hb, "w", encoding="utf-8") as f:
                        json.dump(asdict(updated), f)
                        f.flush()
                        os.fsync(f.fileno())
                    # Guard against overwriting a lock already reclaimed by another process
                    try:
                        current_disk = json.loads(self.lock_path.read_text(encoding="utf-8"))
                        if current_disk.get("nonce") != self.current_payload.nonce:
                            tmp_hb.unlink(missing_ok=True)
                            self.held = False
                            break
                    except Exception:
                        pass
                    os.replace(tmp_hb, self.lock_path)
                    self.current_payload = updated
                except Exception:
                    pass

        self._heartbeat_thread = threading.Thread(
            target=_loop, daemon=True, name="DSHLockHeartbeat"
        )
        self._heartbeat_thread.start()

    def release(self) -> bool:
        if not self.held or not self.current_payload:
            return False

        self._stop_heartbeat.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)

        success = False
        try:
            if self.lock_path.exists():
                raw = self.lock_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if (
                    data.get("nonce") == self.current_payload.nonce
                    and data.get("pid") == self.current_payload.pid
                    and data.get("session_id") == self.current_payload.session_id
                ):
                    self.lock_path.unlink(missing_ok=True)
                    success = True
        except Exception:
            success = False
        finally:
            self.held = False
            self.current_payload = None
        return success


# -----------------------------------------------------------------------------
# MMPP Layer 2: Provenance Ledger & Rollback Guard
# -----------------------------------------------------------------------------

class ProvenanceLedger:
    """Tracks filesystem mutation deltas, detects unauthorized edits, and rolls them back."""

    IGNORE_DIRS = {
        ".git", ".agents", "scratch", "node_modules", "build", "dist",
        ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache",
        ".ruff_cache", ".tox", ".hypothesis", "htmlcov",
    }
    IGNORE_EXTS = {".pyc", ".pyo", ".pyd"}
    IGNORE_FILES = {".dsh_audit.lock", ".agy_provenance.jsonl", ".coverage"}

    @classmethod
    def should_ignore(cls, path: Path) -> bool:
        for part in path.parts:
            if part in cls.IGNORE_DIRS or part.endswith(".egg-info"):
                return True
        if path.suffix.lower() in cls.IGNORE_EXTS:
            return True
        name = path.name
        if (
            name in cls.IGNORE_FILES
            or name.startswith(".coverage.")
            or name.endswith((".tmp", ".reclaim"))
        ):
            return True
        return False

    @classmethod
    def take_snapshot(
        cls,
        root_dir: Path,
        mtime_cache: Optional[Dict[str, Tuple[str, float]]] = None,
    ) -> Dict[str, Tuple[str, float]]:
        """Map normalized relative path -> (sha256, mtime), using mtime cache when unchanged."""
        snapshot: Dict[str, Tuple[str, float]] = {}
        root_resolved = root_dir.resolve()
        for root, dirs, files in os.walk(root_resolved):
            dirs[:] = [
                d for d in dirs if d not in cls.IGNORE_DIRS and not d.endswith(".egg-info")
            ]
            for file_name in files:
                p = Path(root) / file_name
                if cls.should_ignore(p):
                    continue
                try:
                    rel = os.path.normcase(str(p.relative_to(root_resolved)).replace("\\", "/"))
                    mtime = p.stat().st_mtime
                    if mtime_cache and rel in mtime_cache and mtime_cache[rel][1] == mtime:
                        snapshot[rel] = mtime_cache[rel]
                        continue
                    h = hashlib.sha256()
                    with open(p, "rb") as f:
                        while chunk := f.read(65536):
                            h.update(chunk)
                    entry = (h.hexdigest(), mtime)
                    snapshot[rel] = entry
                    if mtime_cache is not None:
                        mtime_cache[rel] = entry
                except (OSError, PermissionError):
                    pass
        return snapshot

    @classmethod
    def compute_delta(
        cls,
        before: Dict[str, Tuple[str, float]],
        after: Dict[str, Tuple[str, float]],
    ) -> List[Dict[str, Any]]:
        deltas: List[Dict[str, Any]] = []
        before_keys = set(before.keys())
        after_keys = set(after.keys())

        for k in sorted(after_keys - before_keys):
            deltas.append({"type": "CREATED", "path": k, "sha256_after": after[k][0]})

        for k in sorted(before_keys - after_keys):
            deltas.append({"type": "DELETE", "path": k, "sha256_before": before[k][0]})

        for k in sorted(before_keys & after_keys):
            if before[k][0] != after[k][0]:
                deltas.append(
                    {
                        "type": "MODIFY",
                        "path": k,
                        "sha256_before": before[k][0],
                        "sha256_after": after[k][0],
                    }
                )
        return deltas

    @classmethod
    def backup_dirty_files(
        cls,
        repo_root: Path,
        scratch_dir: Path,
        session_id: str,
        max_bytes: int = 10 * 1024 * 1024,
    ) -> Optional[Path]:
        """Back up uncommitted modified and untracked files before Tier 1/2 execution."""
        try:
            raw = subprocess.check_output(
                ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
                cwd=str(repo_root),
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return None

        backup_root = scratch_dir / "rollback_backups" / session_id
        tokens = raw.decode("utf-8", errors="replace").split("\0")
        idx = 0
        copied = False
        while idx < len(tokens):
            entry = tokens[idx]
            idx += 1
            if not entry or len(entry) < 4:
                continue
            xy = entry[:2]
            rel = entry[3:].replace("\\", "/")
            if xy[0] in ("R", "C") and idx < len(tokens):
                idx += 1
            rel_path = Path(rel)
            if any(part in cls.IGNORE_DIRS for part in rel_path.parts):
                continue
            src = repo_root / rel_path
            if cls.should_ignore(src) or not src.is_file():
                continue
            try:
                if src.stat().st_size > max_bytes:
                    sys.stderr.write(
                        f"[WARN] Skipping Tier 1/2 dirty backup for oversized file (>{max_bytes} bytes): {rel_path}\n"
                    )
                    continue
                dest = backup_root / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                copied = True
            except OSError:
                pass
        return backup_root if copied else None

    @classmethod
    def detect_blind_overwrites(
        cls,
        deltas: List[Dict[str, Any]],
        tier: WorkspaceTier,
        allowed_paths: List[str],
        repo_root: Path,
        backup_dir: Optional[Path] = None,
    ) -> List[Dict[str, Any]]:
        """Identify unauthorized mutations and roll them back safely (preserving dirty Agy work)."""
        unauthorized: List[Dict[str, Any]] = []
        allowed_norm = {
            os.path.normcase(os.path.normpath(p).replace("\\", "/")) for p in allowed_paths
        }

        for delta in deltas:
            p_str = delta["path"]
            norm_p = os.path.normcase(os.path.normpath(p_str).replace("\\", "/"))
            # Both Tier 1 (in-place) and Tier 2 (mounted --add-dir) forbid unapproved repo_root mutations
            enforce_repo_guard = tier in (
                WorkspaceTier.TIER_1_IN_PLACE,
                WorkspaceTier.TIER_2_SCRATCH_SANDBOX,
            )
            is_allowed = (not enforce_repo_guard) or (norm_p in allowed_norm)
            if not is_allowed:
                unauthorized.append(delta)
                full_path = Path(normalize_path(repo_root / p_str))
                if delta["type"] == "CREATED":
                    try:
                        if full_path.exists():
                            os.chmod(full_path, stat.S_IWRITE)
                            full_path.unlink()
                    except OSError:
                        pass
                elif delta["type"] in ("MODIFY", "DELETE"):
                    backup_file = (backup_dir / p_str) if backup_dir else None
                    if backup_file and backup_file.is_file():
                        try:
                            full_path.parent.mkdir(parents=True, exist_ok=True)
                            if full_path.exists():
                                os.chmod(full_path, stat.S_IWRITE)
                            shutil.copy2(backup_file, full_path)
                            continue
                        except OSError:
                            pass
                    safe_git_checkout(repo_root, p_str)

        return unauthorized

    @classmethod
    def append_to_ledger(cls, repo_root: Path, records: List[ProvenanceRecord]) -> None:
        """Append audit events to .agy_provenance.jsonl."""
        if not records:
            return
        ledger_path = repo_root / ".agy_provenance.jsonl"
        lines = [json.dumps(asdict(r), ensure_ascii=False) + "\n" for r in records]
        try:
            with open(ledger_path, "a", encoding="utf-8") as f:
                f.writelines(lines)
                f.flush()
        except OSError as exc:
            sys.stderr.write(f"[WARN] Failed to write provenance ledger: {exc}\n")


# -----------------------------------------------------------------------------
# DWR Layer 3: Dynamic Workspace Resolver
# -----------------------------------------------------------------------------

class DynamicWorkspaceResolver:
    """Manages workspace lifecycle across in-place, sandbox, and shadow worktree tiers."""

    def __init__(
        self,
        repo_root: Path,
        scratch_dir: Optional[Path] = None,
        auto_sweep: bool = True,
    ):
        self.repo_root = repo_root.resolve()
        self.scratch_dir = (scratch_dir or (self.repo_root / "scratch")).resolve()
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self._deferred_file = self.scratch_dir / ".deferred_cleanups.txt"
        if auto_sweep:
            self.sweep_deferred_cleanups()

    def purge_directory_robust(self, dir_path: Path, max_retries: int = 4) -> bool:
        """Purge directory resiliently with exponential backoff and read-only attribute reset."""
        if not dir_path.exists():
            return True
        delays = [0.0, 0.15, 0.35, 0.75]

        def _handle_readonly(action: Any, path_str: str, exc_info: Any) -> None:
            try:
                os.chmod(path_str, stat.S_IWRITE | stat.S_IREAD)
                action(path_str)
            except Exception:
                pass

        for attempt in range(max_retries):
            if attempt > 0:
                time.sleep(delays[min(attempt, len(delays) - 1)])
            try:
                if sys.version_info >= (3, 12):
                    shutil.rmtree(
                        dir_path,
                        onexc=lambda func, p, exc: _handle_readonly(func, p, exc),
                    )
                else:
                    shutil.rmtree(
                        dir_path,
                        onerror=lambda func, p, exc: _handle_readonly(func, p, exc),
                    )
                if not dir_path.exists():
                    return True
            except Exception:
                pass
        return not dir_path.exists()

    def sweep_deferred_cleanups(self) -> SweepReport:
        """FR-021: Purge abandoned sandboxes and deferred cleanup entries on startup."""
        report = SweepReport()
        retained_lines: List[str] = []
        if self._deferred_file.exists():
            try:
                content = self._deferred_file.read_text(encoding="utf-8")
                lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
            except Exception as exc:
                report.errors.append(f"Failed to read deferred cleanups: {exc}")
                lines = []

            for line in lines:
                report.entries_processed += 1
                parts = line.split("|")
                if len(parts) != 4:
                    continue
                sb_path_str, pid_str, _, iso_ts = parts
                sb_path = Path(sb_path_str)
                try:
                    pid = int(pid_str)
                except ValueError:
                    pid = 0

                alive = is_process_alive(pid) if pid > 0 else False
                age_sec = 0.0
                try:
                    ts = datetime.fromisoformat(iso_ts).timestamp()
                    age_sec = max(0.0, time.time() - ts)
                except Exception:
                    pass

                if alive and age_sec > 3600.0:
                    terminate_process_tree(pid)
                    report.killed_zombies += 1
                    alive = False

                if not alive:
                    if self.purge_directory_robust(sb_path):
                        report.entries_purged += 1
                    else:
                        report.entries_deferred += 1
                        retained_lines.append(line)
                else:
                    report.entries_deferred += 1
                    retained_lines.append(line)

            try:
                if retained_lines:
                    tmp_file = self._deferred_file.with_suffix(".tmp")
                    tmp_file.write_text("\n".join(retained_lines) + "\n", encoding="utf-8")
                    os.replace(tmp_file, self._deferred_file)
                elif self._deferred_file.exists():
                    self._deferred_file.unlink()
            except Exception as exc:
                report.errors.append(f"Atomic update of deferred cleanups failed: {exc}")

        now = time.time()
        for candidate in self.scratch_dir.glob("dsh_sandbox_*"):
            if not candidate.is_dir():
                continue
            if (candidate / ".audit_failure_evidence").exists():
                report.retained_failures += 1
                continue
            try:
                mtime = candidate.stat().st_mtime
                if (now - mtime) > 86400.0:
                    if self.purge_directory_robust(candidate):
                        report.orphans_purged += 1
                    else:
                        report.errors.append(f"Failed to purge orphan sandbox: {candidate}")
            except Exception as exc:
                report.errors.append(f"Orphan inspection failed for {candidate}: {exc}")

        return report

    def evaluate_tier(
        self,
        category: AuditCategory,
        read_only: bool = False,
        tier_override: Optional[WorkspaceTier] = None,
    ) -> WorkspaceTier:
        if tier_override is not None:
            return tier_override
        if read_only or category in (AuditCategory.STATIC_AUDIT, AuditCategory.TEST_EXISTING):
            return WorkspaceTier.TIER_1_IN_PLACE
        if category in (
            AuditCategory.BUG_REPRODUCE,
            AuditCategory.DB_CONCURRENCY,
            AuditCategory.ISOLATED_PROBE,
            AuditCategory.STRESS_TEST,
        ):
            return WorkspaceTier.TIER_2_SCRATCH_SANDBOX
        if category in (AuditCategory.REFACTOR_EVAL, AuditCategory.SPECULATIVE_FIX):
            return WorkspaceTier.TIER_3_SHADOW_WORKTREE
        return WorkspaceTier.TIER_2_SCRATCH_SANDBOX

    def default_timeout_for(self, category: AuditCategory) -> float:
        mapping = {
            AuditCategory.STATIC_AUDIT: 30.0,
            AuditCategory.TEST_EXISTING: 60.0,
            AuditCategory.BUG_REPRODUCE: 60.0,
            AuditCategory.DB_CONCURRENCY: 120.0,
            AuditCategory.ISOLATED_PROBE: 60.0,
            AuditCategory.STRESS_TEST: 120.0,
            AuditCategory.REFACTOR_EVAL: 180.0,
            AuditCategory.SPECULATIVE_FIX: 180.0,
        }
        return mapping.get(category, 60.0)

    def provision_workspace(self, tier: WorkspaceTier, session_id: str) -> WorkspaceContext:
        if tier == WorkspaceTier.TIER_1_IN_PLACE:
            return WorkspaceContext(
                tier=tier,
                workspace_path=self.repo_root,
                repo_root=self.repo_root,
                session_id=session_id,
            )
        if tier == WorkspaceTier.TIER_2_SCRATCH_SANDBOX:
            ts = int(time.time())
            sandbox_path = self.scratch_dir / f"dsh_sandbox_{session_id}_{ts}"
            sandbox_path.mkdir(parents=True, exist_ok=True)
            return WorkspaceContext(
                tier=tier,
                workspace_path=sandbox_path,
                repo_root=self.repo_root,
                session_id=session_id,
            )
        if tier == WorkspaceTier.TIER_3_SHADOW_WORKTREE:
            shadow_path = self.scratch_dir / "shadow_worktrees" / f"dsh_shadow_{session_id}"
            shadow_path.parent.mkdir(parents=True, exist_ok=True)
            safe_git_worktree_add(self.repo_root, shadow_path, ref="HEAD")
            base_sha = self._sync_working_tree_overlay(shadow_path)
            return WorkspaceContext(
                tier=tier,
                workspace_path=shadow_path,
                repo_root=self.repo_root,
                session_id=session_id,
                shadow_branch=base_sha,
            )
        raise ValueError(f"Unsupported WorkspaceTier: {tier}")

    def _sync_working_tree_overlay(self, shadow_path: Path) -> Optional[str]:
        """Mirror Agy's uncommitted tracked/untracked edits into the detached shadow worktree."""
        try:
            raw = subprocess.check_output(
                ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
                cwd=str(self.repo_root),
                stderr=subprocess.DEVNULL,
            )
            tokens = raw.decode("utf-8", errors="replace").split("\0")
            idx = 0
            synced_any = False
            while idx < len(tokens):
                entry = tokens[idx]
                idx += 1
                if not entry or len(entry) < 4:
                    continue
                xy = entry[:2]
                rel = entry[3:].replace("\\", "/")
                if xy[0] in ("R", "C") and idx < len(tokens):
                    orig_rel = tokens[idx].replace("\\", "/")
                    idx += 1
                    orig_dest = shadow_path / orig_rel
                    if orig_dest.is_file():
                        orig_dest.unlink(missing_ok=True)
                        synced_any = True

                rel_path = Path(rel)
                if any(part in ProvenanceLedger.IGNORE_DIRS for part in rel_path.parts):
                    continue
                src_file = self.repo_root / rel_path
                if ProvenanceLedger.should_ignore(src_file):
                    continue

                dest_file = shadow_path / rel_path
                if "D" in xy and not src_file.exists():
                    if dest_file.is_file():
                        dest_file.unlink(missing_ok=True)
                        synced_any = True
                elif src_file.is_file():
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_file)
                    synced_any = True

            if synced_any:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(shadow_path),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                subprocess.run(
                    [
                        "git",
                        "-c",
                        "user.name=Agy",
                        "-c",
                        "user.email=agy@local",
                        "commit",
                        "--allow-empty",
                        "-m",
                        "agy-pre-audit-sync",
                    ],
                    cwd=str(shadow_path),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=str(shadow_path),
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            return None

    def teardown_workspace(
        self,
        context: WorkspaceContext,
        success: bool,
        child_pid: Optional[int] = None,
    ) -> CleanupSummary:
        if child_pid and is_process_alive(child_pid):
            terminate_process_tree(child_pid)

        if context.tier == WorkspaceTier.TIER_1_IN_PLACE:
            return CleanupSummary(
                tier=context.tier,
                workspace_path=context.workspace_path,
                purged=False,
                details="Tier 1 in-place workspace verified.",
            )

        if context.tier == WorkspaceTier.TIER_2_SCRATCH_SANDBOX:
            if success:
                purged = self.purge_directory_robust(context.workspace_path)
                if purged:
                    return CleanupSummary(
                        tier=context.tier,
                        workspace_path=context.workspace_path,
                        purged=True,
                        details="Purged sandbox.",
                    )
                sys.stderr.write(
                    f"[WARN] Sandbox locked; deferring cleanup: {context.workspace_path}\n"
                )
                with open(self._deferred_file, "a", encoding="utf-8") as f:
                    f.write(
                        f"{context.workspace_path}|{child_pid or 0}|{context.session_id}|{datetime.now(timezone.utc).isoformat()}\n"
                    )
                return CleanupSummary(
                    tier=context.tier,
                    workspace_path=context.workspace_path,
                    purged=False,
                    deferred=True,
                    details="Purge failed; registered for deferred cleanup.",
                )

            ev_file = context.workspace_path / ".audit_failure_evidence"
            try:
                ev_file.write_text(
                    json.dumps(
                        {
                            "session_id": context.session_id,
                            "failed_at": datetime.now(timezone.utc).isoformat(),
                            "retained": True,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass
            return CleanupSummary(
                tier=context.tier,
                workspace_path=context.workspace_path,
                purged=False,
                evidence_path=context.workspace_path,
                details="Failure evidence retained.",
            )

        if context.tier == WorkspaceTier.TIER_3_SHADOW_WORKTREE:
            patch_path = None
            patch_sha256 = None
            try:
                base_ref = context.shadow_branch or subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(self.repo_root),
                    text=True,
                    stderr=subprocess.PIPE,
                ).strip()
                # Stage intent-to-add in isolated worktree only so newly created untracked files appear in diff
                subprocess.run(
                    ["git", "add", "-N", "."],
                    cwd=str(context.workspace_path),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                patch_text = subprocess.check_output(
                    ["git", "diff", base_ref],
                    cwd=str(context.workspace_path),
                    text=True,
                    stderr=subprocess.PIPE,
                )

                if patch_text.strip():
                    patches_dir = self.scratch_dir / "patches"
                    patches_dir.mkdir(parents=True, exist_ok=True)
                    patch_path = patches_dir / f"dsh_patch_{context.session_id}.patch"
                    patch_path.write_text(patch_text, encoding="utf-8")
                    patch_sha256 = hashlib.sha256(patch_text.encode("utf-8")).hexdigest()
            except Exception:
                pass

            purged_wt = False
            for delay in (0.2, 0.5, 1.0):
                try:
                    ensure_git_index_unlocked(self.repo_root)
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", str(context.workspace_path)],
                        cwd=str(self.repo_root),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                    purged_wt = True
                    break
                except subprocess.SubprocessError:
                    time.sleep(delay + random.uniform(0.01, 0.05))

            ensure_git_index_unlocked(self.repo_root)
            try:
                subprocess.run(
                    ["git", "worktree", "prune"],
                    cwd=str(self.repo_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except (subprocess.SubprocessError, OSError):
                pass
            if context.workspace_path.exists():
                purged_wt = self.purge_directory_robust(context.workspace_path)
            if not purged_wt and context.workspace_path.exists():
                sys.stderr.write(
                    f"[WARN] Shadow worktree locked; deferring cleanup: {context.workspace_path}\n"
                )
                with open(self._deferred_file, "a", encoding="utf-8") as f:
                    f.write(
                        f"{context.workspace_path}|{child_pid or 0}|{context.session_id}|{datetime.now(timezone.utc).isoformat()}\n"
                    )

            return CleanupSummary(
                tier=context.tier,
                workspace_path=context.workspace_path,
                purged=purged_wt,
                deferred=(not purged_wt and context.workspace_path.exists()),
                patch_path=patch_path,
                details=f"Worktree removed (purged={purged_wt}, patch_sha256={patch_sha256}).",
            )

        return CleanupSummary(
            tier=context.tier,
            workspace_path=context.workspace_path,
            purged=False,
            details="Unknown tier.",
        )


# -----------------------------------------------------------------------------
# MMPP Layer 3: Context Injector & Session Manager
# -----------------------------------------------------------------------------

class ContextInjector:
    """Prepends immutable boundary constraints and redacts secrets prior to dispatch."""

    @staticmethod
    def build_injected_prompt(
        task: AuditTask,
        context: WorkspaceContext,
        session_state: Optional[SessionState] = None,
        recent_agy_files: Optional[List[str]] = None,
    ) -> str:
        recent_str = (
            "\n".join(f"   - {f}" for f in recent_agy_files)
            if recent_agy_files
            else "   (none recorded)"
        )
        if task.read_only and task.target_paths:
            targets_str = f"{', '.join(task.target_paths)} (READ-ONLY inspection scope; NO writes allowed)"
        elif task.target_paths:
            targets_str = ", ".join(task.target_paths)
        else:
            targets_str = "(strictly read-only in Tier 1; sandbox/worktree only in Tier 2/3)"
        turn_num = (session_state.turn_count + 1) if session_state else 1
        mounted = (
            str(context.repo_root)
            if context.tier == WorkspaceTier.TIER_2_SCRATCH_SANDBOX
            else "N/A"
        )

        header = f"""=== EMPIRICAL AUDIT TASK DISPATCH ===
Originator: Antigravity Orchestrator (Agy)
Session ID: {context.session_id} | Turn: {turn_num}
Workspace Tier: {context.tier.value} ({context.workspace_path})

### READ-ONLY INVARIANTS (STRICTLY PROHIBITED FROM MODIFICATION):
   - GEMINI.md, .cursorrules, hooks.json, setup.bat
   - .agents/teamwork/*
   - .git/*
   - Target Paths Scope: {targets_str}

### AUTHORIZED WORKSPACE:
   - Primary CWD: {context.workspace_path}
   - Mounted Repo Root: {mounted}
   - Strict Read-Only Mode: {task.read_only}

### RECENT MODIFICATIONS BY AGY:
{recent_str}

### EMPIRICAL AUDIT DIRECTIVE:
{task.task_prompt.strip()}
======================================"""
        return redact_credentials(header)


class SessionManager:
    """Manages persistent multi-turn DSH session state."""

    def __init__(self, scratch_dir: Path):
        self.scratch_dir = scratch_dir
        self.state_file = self.scratch_dir / "dsh_sessions.json"
        self._sessions: Dict[str, SessionState] = {}
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                for s_id, s_data in data.items():
                    self._sessions[s_id] = SessionState(
                        session_id=s_data["session_id"],
                        created_at=s_data["created_at"],
                        last_turn_at=s_data["last_turn_at"],
                        turn_count=s_data["turn_count"],
                        tier=WorkspaceTier(s_data["tier"]),
                        cumulative_tokens=s_data.get(
                            "cumulative_tokens",
                            {"total": 0, "input": 0, "output": 0, "cache_read": 0},
                        ),
                    )
            except Exception:
                self._sessions = {}

    def _save(self) -> None:
        try:
            self.scratch_dir.mkdir(parents=True, exist_ok=True)
            data = {
                s_id: {
                    "session_id": st.session_id,
                    "created_at": st.created_at,
                    "last_turn_at": st.last_turn_at,
                    "turn_count": st.turn_count,
                    "tier": st.tier.value,
                    "cumulative_tokens": st.cumulative_tokens,
                }
                for s_id, st in self._sessions.items()
            }
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp, self.state_file)
        except Exception:
            pass

    def get_or_create_session(
        self, session_id: Optional[str], tier: WorkspaceTier
    ) -> Tuple[SessionState, bool]:
        now_iso = datetime.now(timezone.utc).isoformat()
        if session_id and session_id in self._sessions:
            return self._sessions[session_id], True

        sid = session_id or f"session-{uuid.uuid4().hex[:12]}"
        new_state = SessionState(
            session_id=sid,
            created_at=now_iso,
            last_turn_at=now_iso,
            turn_count=0,
            tier=tier,
            cumulative_tokens={"total": 0, "input": 0, "output": 0, "cache_read": 0},
        )
        self._sessions[sid] = new_state
        self._save()
        return new_state, False

    def record_turn(self, session_id: str, token_usage: Dict[str, int]) -> SessionState:
        if session_id not in self._sessions:
            state, _ = self.get_or_create_session(
                session_id, WorkspaceTier.TIER_2_SCRATCH_SANDBOX
            )
        else:
            state = self._sessions[session_id]

        state.turn_count += 1
        state.last_turn_at = datetime.now(timezone.utc).isoformat()
        for k in ("total", "input", "output", "cache_read"):
            state.cumulative_tokens[k] = state.cumulative_tokens.get(k, 0) + token_usage.get(
                k, 0
            )
        self._save()
        return state


# -----------------------------------------------------------------------------
# NDJSON Stream Parser & Tri-Thread Streaming Execution
# -----------------------------------------------------------------------------

class NDJSONStreamParser:
    """Line-by-line FSM parser for DSH headless --json NDJSON events."""

    def __init__(self):
        self.tool_calls: Dict[str, ToolCallRecord] = {}
        self.text_chunks: List[str] = []
        self.thinking_chunks: List[str] = []
        self.final_text: Optional[str] = None
        self.final_received: bool = False
        self.last_usage: Dict[str, int] = {
            "total": 0,
            "input": 0,
            "output": 0,
            "cache_read": 0,
        }
        self.unknown_session_detected: bool = False
        self.session_id: Optional[str] = None
        self.error_message: Optional[str] = None

    @property
    def cache_hit_rate(self) -> float:
        total = self.last_usage.get("total", 0)
        cache_read = self.last_usage.get("cache_read", 0)
        return round((cache_read / total) * 100.0, 2) if total > 0 else 0.0

    def feed_line(self, line: str) -> Optional[DSHRunEvent]:
        raw = line.strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return None
        except Exception:
            sys.stderr.write(f"[DSH Parser EC-007 Warning] Non-JSON stdout: {raw[:160]}\n")
            sys.stderr.flush()
            return None

        etype = payload.get("type", "unknown")
        event = DSHRunEvent(event_type=etype, data=payload, raw_line=raw)

        if etype == "session":
            self.session_id = payload.get("sessionId")
        elif etype == "status":
            usage = payload.get("usage", {})
            if isinstance(usage, dict) and usage:
                def _safe_int(val: Any) -> int:
                    try:
                        return int(val) if val is not None else 0
                    except (TypeError, ValueError):
                        return 0

                self.last_usage = {
                    "total": _safe_int(usage.get("totalTokens", 0)),
                    "input": _safe_int(usage.get("inputTokens", 0)),
                    "output": _safe_int(usage.get("outputTokens", 0)),
                    "cache_read": _safe_int(usage.get("cacheReadTokens", 0)),
                }
        elif etype == "tool_call":
            cid = payload.get("callId", "")
            if cid:
                self.tool_calls[cid] = ToolCallRecord(
                    call_id=cid,
                    tool_name=payload.get("tool", "unknown"),
                    arguments=payload.get("input", {}),
                    status="running",
                )
        elif etype == "tool_result":
            cid = payload.get("callId", "")
            res_status = payload.get("status", "completed")
            rec = self.tool_calls.get(cid)
            if not rec:
                rec = ToolCallRecord(call_id=cid, tool_name="unknown")
                self.tool_calls[cid] = rec
            rec.status = res_status
            rec.result = str(payload.get("result", ""))
            rec.is_error = res_status in ("failed", "aborted")
        elif etype == "thinking":
            txt = payload.get("text", "")
            if txt:
                self.thinking_chunks.append(txt)
        elif etype == "text":
            txt = payload.get("text", "")
            if txt:
                self.text_chunks.append(txt)
        elif etype == "final":
            self.final_received = True
            self.session_id = payload.get("sessionId") or self.session_id
            self.final_text = payload.get("text", "")
        elif etype == "error":
            msg = str(payload.get("message", ""))
            self.error_message = msg
            low_msg = msg.lower()
            if (
                "does not exist" in low_msg
                or "unknown session" in low_msg
                or "was recorded in" in low_msg
            ):
                self.unknown_session_detected = True

        return event


def execute_streaming_subprocess(
    cmd_args: List[str],
    injected_prompt: str,
    cwd: Path,
    timeout_sec: float,
    parser: NDJSONStreamParser,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, List[str], List[str], int, bool]:
    """Execute DSH with concurrent Tri-Thread I/O and active Watchdog Timer."""
    exec_args = list(cmd_args)
    popen_target: Any = exec_args
    if sys.platform.startswith("win") and exec_args and exec_args[0].lower().endswith((".cmd", ".bat")):
        # Windows cmd.exe /c strips first/last quotes when >=2 quoted args exist (e.g. .cmd path + --add-dir with spaces);
        # /d /s /c "..." strips only our explicit outer quotes, keeping inner argument quoting intact.
        popen_target = f'cmd.exe /d /s /c "{subprocess.list2cmdline(exec_args)}"'

    sub_env = os.environ.copy()
    sub_env["ELECTRON_RUN_AS_NODE"] = "1"
    if env:
        sub_env.update(env)

    proc = subprocess.Popen(
        popen_target,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd),
        env=sub_env,
        shell=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    stdout_lines: List[str] = []
    stderr_lines: List[str] = []
    timed_out = [False]

    def feed_stdin() -> None:
        try:
            if proc.stdin:
                proc.stdin.write(injected_prompt)
                proc.stdin.flush()
                proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    def drain_stderr() -> None:
        try:
            if proc.stderr:
                for line in proc.stderr:
                    stderr_lines.append(line.rstrip("\n"))
        except (ValueError, OSError):
            pass

    def on_timeout() -> None:
        timed_out[0] = True
        if proc.pid:
            terminate_process_tree(proc.pid)

    stdin_thread = threading.Thread(target=feed_stdin, name="DSH-StdinFeeder", daemon=True)
    stderr_thread = threading.Thread(target=drain_stderr, name="DSH-StderrDrainer", daemon=True)
    stdin_thread.start()
    stderr_thread.start()

    timer = threading.Timer(timeout_sec, on_timeout)
    timer.start()

    try:
        if proc.stdout:
            for line in proc.stdout:
                stripped = line.rstrip("\n")
                stdout_lines.append(stripped)
                try:
                    parser.feed_line(stripped)
                except Exception as exc:
                    sys.stderr.write(f"[DSH Parser Warning] Line parse error: {exc}\n")
    finally:
        timer.cancel()
        stdin_thread.join(timeout=2.0)
        stderr_thread.join(timeout=2.0)
        if proc.poll() is None:
            try:
                terminate_process_tree(proc.pid)
            except Exception:
                pass
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            try:
                if proc.pid:
                    terminate_process_tree(proc.pid)
                proc.kill()
                proc.wait(timeout=2.0)
            except Exception:
                pass

    exit_code = proc.returncode if proc.returncode is not None else -1
    return exit_code, stdout_lines, stderr_lines, proc.pid or -1, timed_out[0]


# -----------------------------------------------------------------------------
# High-Level Orchestrator Client & CLI
# -----------------------------------------------------------------------------

class DSHAuditorClient:
    """High-level empirical peer auditor coordinating DWR, MMPP, and DSH CLI."""

    def __init__(self, repo_root: Optional[Path] = None, auto_sweep: bool = True):
        self.repo_root = (repo_root or find_repo_root()).resolve()
        self.dwr = DynamicWorkspaceResolver(self.repo_root, auto_sweep=auto_sweep)
        self.lock_manager = LockManager(self.repo_root)
        self.session_manager = SessionManager(self.dwr.scratch_dir)

    def _build_cmd_args(
        self,
        dsh_bin: str,
        context: WorkspaceContext,
        resume_session_id: Optional[str],
    ) -> List[str]:
        args = [
            dsh_bin,
            "--profile",
            "headless",
            "--permission-mode",
            "danger-full-access",
            "--approval-policy",
            "never",
            "--json",
        ]
        if context.tier == WorkspaceTier.TIER_2_SCRATCH_SANDBOX:
            args.extend(["--add-dir", str(self.repo_root)])
        if resume_session_id:
            args.extend(["--session-id", resume_session_id])
        args.append("-")
        return args

    def execute_audit(self, task: AuditTask) -> AuditResult:
        start_t = time.time()
        tier = self.dwr.evaluate_tier(task.category, task.read_only, task.tier_override)
        timeout = task.timeout_sec or self.dwr.default_timeout_for(task.category)

        session_state, _ = self.session_manager.get_or_create_session(task.session_id, tier)
        resume_id = task.session_id if task.session_id else None

        try:
            dsh_bin = resolve_dsh_binary()
        except DSHBinaryNotFoundError as exc:
            return AuditResult(
                session_id=session_state.session_id,
                category=task.category,
                tier=tier,
                success=False,
                exit_code=-1,
                raw_output="",
                sanitized_output="",
                tool_calls=[],
                token_usage={"total": 0, "input": 0, "output": 0, "cache_read": 0},
                cache_hit_rate=0.0,
                duration_sec=round(time.time() - start_t, 2),
                workspace_path=str(self.repo_root),
                error_message=str(exc),
                task_id=task.task_id,
            )

        try:
            self.lock_manager.acquire(
                session_id=session_state.session_id,
                scope=tier.value,
                timeout_sec=timeout,
            )
        except LockContentionError:
            return AuditResult(
                session_id=session_state.session_id,
                category=task.category,
                tier=tier,
                success=False,
                exit_code=-1,
                raw_output="",
                sanitized_output="",
                tool_calls=[],
                token_usage={"total": 0, "input": 0, "output": 0, "cache_read": 0},
                cache_hit_rate=0.0,
                duration_sec=round(time.time() - start_t, 2),
                workspace_path=str(self.repo_root),
                error_message="LOCK_CONTENTION_TIMEOUT",
                task_id=task.task_id,
            )
        backup_dir: Optional[Path] = None
        context: Optional[WorkspaceContext] = None
        cleanup: Optional[CleanupSummary] = None
        child_pid: Optional[int] = None
        try:
            before_snapshot: Dict[str, Tuple[str, float]] = {}
            if tier in (WorkspaceTier.TIER_1_IN_PLACE, WorkspaceTier.TIER_2_SCRATCH_SANDBOX):
                before_snapshot = ProvenanceLedger.take_snapshot(self.repo_root)
                backup_dir = ProvenanceLedger.backup_dirty_files(
                    self.repo_root, self.dwr.scratch_dir, session_state.session_id
                )

            try:
                context = self.dwr.provision_workspace(tier, session_state.session_id)
            except RuntimeError as exc:
                return AuditResult(
                    session_id=session_state.session_id,
                    category=task.category,
                    tier=tier,
                    success=False,
                    exit_code=-1,
                    raw_output="",
                    sanitized_output="",
                    tool_calls=[],
                    token_usage={"total": 0, "input": 0, "output": 0, "cache_read": 0},
                    cache_hit_rate=0.0,
                    duration_sec=round(time.time() - start_t, 2),
                    workspace_path=str(self.repo_root),
                    error_message=str(exc),
                    task_id=task.task_id,
                )

            recent_agy_files: List[str] = []
            try:
                st = subprocess.check_output(
                    ["git", "status", "--porcelain"],
                    cwd=str(self.repo_root),
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                recent_agy_files = [ln[3:].strip() for ln in st.splitlines() if ln.strip()][:10]
            except Exception:
                pass

            injected_prompt = ContextInjector.build_injected_prompt(
                task, context, session_state, recent_agy_files=recent_agy_files
            )

            env = None
            if tier == WorkspaceTier.TIER_2_SCRATCH_SANDBOX:
                existing_pp = os.environ.get("PYTHONPATH", "")
                pp = f"{self.repo_root}{os.pathsep}{self.repo_root / 'scripts'}"
                env = {"PYTHONPATH": f"{pp}{os.pathsep}{existing_pp}" if existing_pp else pp}

            parser = NDJSONStreamParser()

            exit_code, stdout_lines, stderr_lines, child_pid, timed_out = (
                execute_streaming_subprocess(
                    self._build_cmd_args(dsh_bin, context, resume_id),
                    injected_prompt,
                    cwd=context.workspace_path,
                    timeout_sec=timeout,
                    parser=parser,
                    env=env,
                )
            )

            # EC-013: Unknown/expired session ID fallback retry once as fresh Turn 1
            stderr_joined = "\n".join(stderr_lines)
            if (
                parser.unknown_session_detected
                or (
                    "session" in stderr_joined.lower()
                    and (
                        "does not exist" in stderr_joined.lower()
                        or "was recorded in" in stderr_joined.lower()
                    )
                )
            ) and resume_id:
                sys.stderr.write(
                    f"[WARN] Unknown session '{resume_id}' detected; retrying fresh Turn 1.\n"
                )
                parser = NDJSONStreamParser()
                exit_code, stdout_lines, stderr_lines, child_pid, timed_out = (
                    execute_streaming_subprocess(
                        self._build_cmd_args(dsh_bin, context, None),
                        injected_prompt,
                        cwd=context.workspace_path,
                        timeout_sec=timeout,
                        parser=parser,
                        env=env,
                    )
                )

            actual_session_id = parser.session_id or session_state.session_id
            error_msg = parser.error_message
            if timed_out:
                error_msg = f"EXECUTION_TIMEOUT after {timeout}s"
            elif exit_code != 0 and error_msg is None and stderr_lines:
                error_msg = "\n".join(stderr_lines[-5:]).strip() or None

            # EC-015: Fail-soft if stream severed without final or text response
            success = (
                not timed_out
                and exit_code == 0
                and error_msg is None
                and (parser.final_received or bool(parser.text_chunks))
            )

            unauthorized: List[Dict[str, Any]] = []
            deltas: List[Dict[str, Any]] = []
            if tier in (WorkspaceTier.TIER_1_IN_PLACE, WorkspaceTier.TIER_2_SCRATCH_SANDBOX):
                post_snapshot = ProvenanceLedger.take_snapshot(
                    self.repo_root, mtime_cache=dict(before_snapshot)
                )
                deltas = ProvenanceLedger.compute_delta(before_snapshot, post_snapshot)
                effective_allowed_paths = [] if task.read_only else task.target_paths
                unauthorized = ProvenanceLedger.detect_blind_overwrites(
                    deltas, tier, effective_allowed_paths, self.repo_root, backup_dir=backup_dir
                )
                if unauthorized:
                    success = False
                    error_msg = "VIOLATION_TIER1_UNAUTHORIZED_MUTATION"

            now_iso = datetime.now(timezone.utc).isoformat()
            prov_records: List[ProvenanceRecord] = [
                ProvenanceRecord(
                    session_id=actual_session_id,
                    tier=tier.value,
                    timestamp=now_iso,
                    event_type="AUDIT_EXECUTION",
                    details={
                        "category": task.category.value,
                        "success": success,
                        "exit_code": exit_code,
                        "deltas_count": len(deltas),
                        "unauthorized_count": len(unauthorized),
                    },
                )
            ]
            for d in deltas:
                prov_records.append(
                    ProvenanceRecord(
                        session_id=actual_session_id,
                        tier=tier.value,
                        timestamp=now_iso,
                        event_type="ROLLBACK" if d in unauthorized else "MUTATION",
                        details=d,
                    )
                )
            ProvenanceLedger.append_to_ledger(self.repo_root, prov_records)

            cleanup = self.dwr.teardown_workspace(
                context, success=success, child_pid=child_pid
            )
            self.session_manager.record_turn(actual_session_id, parser.last_usage)

            raw_output = "\n".join(stdout_lines)
            verdict = parser.final_text if parser.final_text is not None else "\n".join(parser.text_chunks)
            sanitized_output = redact_credentials(verdict)

            return AuditResult(
                session_id=actual_session_id,
                category=task.category,
                tier=tier,
                success=success,
                exit_code=exit_code,
                raw_output=raw_output,
                sanitized_output=sanitized_output,
                tool_calls=list(parser.tool_calls.values()),
                token_usage=parser.last_usage,
                cache_hit_rate=parser.cache_hit_rate,
                duration_sec=round(time.time() - start_t, 2),
                workspace_path=str(context.workspace_path),
                evidence_path=str(cleanup.evidence_path) if cleanup.evidence_path else None,
                patch_path=str(cleanup.patch_path) if cleanup.patch_path else None,
                unauthorized_mutations=unauthorized,
                error_message=error_msg,
                task_id=task.task_id,
            )
        finally:
            if context is not None and cleanup is None:
                try:
                    self.dwr.teardown_workspace(context, success=False, child_pid=child_pid)
                except Exception as exc:
                    sys.stderr.write(f"[WARN] Emergency workspace teardown failed: {exc}\n")
            if backup_dir and backup_dir.exists():
                self.dwr.purge_directory_robust(backup_dir)
                try:
                    backup_dir.parent.rmdir()
                except OSError:
                    pass
            self.lock_manager.release()


def run_empirical_audit(
    prompt: str,
    session_id: Optional[str] = None,
    cwd: Optional[str] = None,
    timeout: int = 120,
    verbose: bool = True,
    category: AuditCategory = AuditCategory.BUG_REPRODUCE,
) -> Dict[str, Any]:
    """Backwards-compatible convenience wrapper returning a structured summary dict."""
    client = DSHAuditorClient(repo_root=Path(cwd) if cwd else None)
    task = AuditTask(
        category=category,
        task_prompt=prompt,
        session_id=session_id,
        timeout_sec=float(timeout),
    )
    result = client.execute_audit(task)

    output = {
        "session_id": result.session_id,
        "tool_calls": [asdict(tc) for tc in result.tool_calls],
        "final_text": result.sanitized_output,
        "duration_sec": result.duration_sec,
        "exit_code": result.exit_code,
        "success": result.success,
        "error": result.error_message,
        "cache_hit_rate": result.cache_hit_rate,
        "tier": result.tier.value,
        "evidence_path": result.evidence_path,
        "patch_path": result.patch_path,
    }
    if verbose:
        print(f"Session ID: {result.session_id} | Tier: {result.tier.value} | Duration: {result.duration_sec}s")
        print(result.sanitized_output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="DSH Empirical Peer Auditor CLI")
    parser.add_argument("prompt", nargs="?", default=None, help="Audit task prompt")
    parser.add_argument("--task", dest="task_opt", default=None, help="Audit task prompt (or stdin if omitted)")
    parser.add_argument(
        "--category",
        type=str.lower,
        choices=[c.value for c in AuditCategory],
        default=AuditCategory.BUG_REPRODUCE.value,
        help="Audit risk category",
    )
    parser.add_argument(
        "--tier",
        type=str.lower,
        choices=[t.value for t in WorkspaceTier],
        default=None,
        help="Explicit workspace tier override",
    )
    parser.add_argument("--session-id", default=None, help="Existing DSH session ID to resume")
    parser.add_argument("--cwd", default=None, help="Repository root directory")
    parser.add_argument("--timeout", type=float, default=None, help="Execution timeout in seconds")
    parser.add_argument("--read-only", action="store_true", help="Enforce Tier 1 read-only mode")
    parser.add_argument(
        "--target-paths",
        action="append",
        default=[],
        help="Allowed relative path (repeatable or comma-separated)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")

    args = parser.parse_args()
    prompt_text = args.task_opt if args.task_opt is not None else args.prompt
    if prompt_text is None:
        if not sys.stdin.isatty():
            prompt_text = sys.stdin.read()
        else:
            parser.error("A prompt via --task, positional argument, or stdin is required.")

    target_paths = [p.strip() for entry in args.target_paths for p in entry.split(",") if p.strip()]

    category = AuditCategory(args.category)
    tier_override = WorkspaceTier(args.tier) if args.tier else None

    task = AuditTask(
        category=category,
        task_prompt=prompt_text,
        session_id=args.session_id,
        target_paths=target_paths,
        tier_override=tier_override,
        read_only=args.read_only,
        timeout_sec=args.timeout,
    )

    client = DSHAuditorClient(repo_root=Path(args.cwd) if args.cwd else None)
    result = client.execute_audit(task)

    payload = {
        "task_id": result.task_id,
        "session_id": result.session_id,
        "category": result.category.value,
        "workspace_tier": result.workspace_tier.value,
        "success": result.success,
        "exit_code": result.exit_code,
        "duration_sec": result.duration_sec,
        "cache_hit_rate": result.cache_hit_rate,
        "total_tokens": result.total_tokens,
        "token_usage": result.token_usage,
        "tool_calls": [asdict(tc) for tc in result.tool_calls],
        "verdict_text": result.verdict_text,
        "workspace_path": result.workspace_path,
        "sandbox_evidence_path": result.sandbox_evidence_path,
        "diff_patch_path": result.diff_patch_path,
        "unauthorized_mutations": result.unauthorized_mutations,
        "error": result.error,
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Session ID: {result.session_id}")
        print(f"Tier: {result.tier.value} | Success: {result.success} | Duration: {result.duration_sec}s")
        if result.error_message:
            print(f"Error: {result.error_message}")
        print(f"\n{result.sanitized_output}\n")
        if result.evidence_path:
            print(f"Evidence retained at: {result.evidence_path}")
        if result.patch_path:
            print(f"Patch saved at: {result.patch_path}")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
