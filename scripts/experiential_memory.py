#!/usr/bin/env python3
"""
Omni-Kernel v3.0: Cross-Session Experiential Memory Engine
Stores, recalls, and prunes proven execution traces (code snippets, bash commands, verified fixes).
Enables the AI to instantly recall verified past solutions across sessions in <0.3ms without re-reasoning.
100% Python Standard Library (Zero dependencies, pure deterministic JSON).
"""

import os
import re
import sys
import json
import time
import hashlib
import errno
import stat
import copy
import threading
import tempfile
from typing import Optional, Dict, List, Any

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_utils import redact_secrets, canonical_workspace_hash

class TracePersistenceError(IOError):
    """Raised when writing or persisting proven traces fails due to I/O or serialization error (VULN-004)."""
    pass

TRACES_FILE = os.path.join(_SCRIPT_DIR, "proven_traces.json")
MAX_TRACES = 250

_CACHE = {}  # abs_path -> {"data": dict, "sig": tuple}
_MEM_LOCK = threading.RLock()


def tokenize(text: str) -> list:
    """Extracts normalized lowercase tokens from text."""
    if not text:
        return []
    cleaned = re.sub(r"[^\w\s\-\.]", " ", text.lower())
    tokens = [t.strip(".-") for t in cleaned.split() if len(t.strip(".-")) > 1]
    return list(set(tokens))


def _get_traces_read_view(traces_path: str = None) -> list:
    """Internal fast read-only view of traces list under _MEM_LOCK for sub-millisecond recall (VULN-103)."""
    global _CACHE, _MEM_LOCK
    path = traces_path or TRACES_FILE
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return []
    with _MEM_LOCK:
        try:
            stat_res = os.stat(abs_path)
            cache_sig = (stat_res.st_mtime_ns, stat_res.st_size, getattr(stat_res, "st_ino", 0))
            cache_entry = _CACHE.get(abs_path)
            if cache_entry is not None and cache_sig == cache_entry.get("sig") and (traces_path is None or traces_path == TRACES_FILE):
                return list(cache_entry["data"].get("traces", []))
            with open(abs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                scrubbed = []
                for tr in data.get("traces", []):
                    try:
                        scrubbed.append(_redact_trace_dict(tr))
                    except Exception as red_err:
                        sys.stderr.write(f"[!] Warning: Dropping unredactable trace {tr.get('id', 'unknown')}: {red_err}\n")
                data["traces"] = scrubbed
                _CACHE[abs_path] = {"data": data, "sig": cache_sig}
                return list(data.get("traces", []))
        except Exception as read_err:
            from memory_utils import persist_diag
            persist_diag(read_err, 256)
            sys.stderr.write(f"[!] Warning: _get_traces_read_view encountered error reading {abs_path}: {read_err}\n")
            return []


def load_traces(traces_path: str = None, bypass_cache: bool = False) -> dict:
    """Loads stored execution traces using (mtime_ns, size, inode) cache guarded by _MEM_LOCK (VULN-003, VULN-004, VULN-103).
    Guarantees isolation against shared mutable state by returning an independent deep copy to public callers.
    """
    global _CACHE, _MEM_LOCK
    path = traces_path or TRACES_FILE
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return {"version": "3.0.0", "updated_at": "", "traces": []}

    with _MEM_LOCK:
        try:
            stat_res = os.stat(abs_path)
            cache_sig = (stat_res.st_mtime_ns, stat_res.st_size, getattr(stat_res, "st_ino", 0))
            cache_entry = _CACHE.get(abs_path)
            if not bypass_cache and cache_entry is not None and cache_sig == cache_entry.get("sig") and (traces_path is None or traces_path == TRACES_FILE):
                return copy.deepcopy(cache_entry["data"])
            with open(abs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                scrubbed = []
                for tr in data.get("traces", []):
                    try:
                        scrubbed.append(_redact_trace_dict(tr))
                    except Exception as red_err:
                        # VULN-003: Fail-closed: Never append raw unredacted trace on redaction error
                        sys.stderr.write(f"[!] Warning: Dropping unredactable trace {tr.get('id', 'unknown')}: {red_err}\n")
                data["traces"] = scrubbed
                _CACHE[abs_path] = {"data": data, "sig": cache_sig}
                return copy.deepcopy(data)
        except json.JSONDecodeError as jde:
            # VULN-004: Corrupt JSON must raise, NOT return empty dict, to prevent overwriting prior traces
            sys.stderr.write(f"[!] LỖI load_traces: Traces file {abs_path} is corrupt JSON: {jde}\n")
            raise ValueError(f"Traces file {abs_path} contains invalid JSON: {jde}") from jde
        except (PermissionError, OSError) as oe:
            sys.stderr.write(f"[!] LỖI load_traces: Cannot read traces file {abs_path}: {oe}\n")
            raise


# Imports hoisted to top of file
import tempfile

_lock_local = threading.local()
_PROCESS_LOCKS: Dict[str, List[Any]] = {}  # path -> [RLock, refcount] (VULN-005)
_PROCESS_LOCKS_MUTEX = threading.Lock()

def _enter_process_rlock(path: str) -> threading.RLock:
    """Acquires a reference to an intra-process RLock for path with refcount tracking (VULN-005)."""
    with _PROCESS_LOCKS_MUTEX:
        if path not in _PROCESS_LOCKS:
            _PROCESS_LOCKS[path] = [threading.RLock(), 0]
        entry = _PROCESS_LOCKS[path]
        entry[1] += 1
        return entry[0]

def _exit_process_rlock(path: str):
    """Releases a reference to an intra-process RLock, pruning entry when refcount hits zero (VULN-005)."""
    with _PROCESS_LOCKS_MUTEX:
        if path in _PROCESS_LOCKS:
            entry = _PROCESS_LOCKS[path]
            entry[1] -= 1
            if entry[1] <= 0:
                del _PROCESS_LOCKS[path]

def _get_process_rlock(path: str) -> threading.RLock:
    with _PROCESS_LOCKS_MUTEX:
        if path not in _PROCESS_LOCKS:
            _PROCESS_LOCKS[path] = [threading.RLock(), 0]
        return _PROCESS_LOCKS[path][0]

try:
    import msvcrt
    def _lock_fd(fd):
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    def _unlock_fd(fd):
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
except ImportError:
    try:
        import fcntl
        def _lock_fd(fd):
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def _unlock_fd(fd):
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
    except ImportError:
        def _lock_fd(fd): pass
        def _unlock_fd(fd): pass


class FileLock:
    """
    Advisory OS-level file lock operating on a dedicated lock file descriptor.
    Includes thread-local reentrancy depth tracking (Hazard 45) and guarantees 1-byte pre-sizing
    and zero-offset seeking prior to locking on Windows NTFS (VULN-003).
    """
    def __init__(self, lock_file: str, timeout: float = 5.0):
        self.lock_file = os.path.abspath(lock_file)
        self._lock_key = os.path.normcase(os.path.realpath(self.lock_file))
        self.timeout = timeout
        self.fd = None
        self._rlock = None

    def __enter__(self):
        # VULN-003 & VULN-005: Acquire process-wide RLock with refcount tracking on canonical key to prevent unbounded registry leak
        self._rlock = _enter_process_rlock(self._lock_key)
        acquired = self._rlock.acquire(timeout=self.timeout)
        if not acquired:
            _exit_process_rlock(self._lock_key)
            self._rlock = None
            raise TimeoutError(f"Could not acquire intra-process thread lock on {self.lock_file} within {self.timeout}s")

        try:
            held = getattr(_lock_local, "held_locks", None)
            if held is None:
                held = _lock_local.held_locks = {}
            if self._lock_key in held:
                held[self._lock_key] += 1
                return self

            deadline = time.monotonic() + self.timeout
            # Step 1: Open file descriptor safely with 0o600 permissions and defend against symlink attacks (VULN-008)
            if os.path.islink(self.lock_file) or (hasattr(os.path, "isreparsepoint") and os.path.isreparsepoint(self.lock_file)):
                raise PermissionError(f"Security violation: lock file cannot be a symbolic link or reparse point: {self.lock_file}")

            open_flags = os.O_CREAT | os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                open_flags |= os.O_NOFOLLOW

            while self.fd is None:
                created_new = False
                try:
                    try:
                        self.fd = os.open(self.lock_file, open_flags | os.O_EXCL, 0o600)
                        created_new = True
                    except FileExistsError:
                        self.fd = os.open(self.lock_file, open_flags, 0o600)

                    st = os.fstat(self.fd)
                    if not stat.S_ISREG(st.st_mode):
                        raise PermissionError(f"Security violation: lock file is not a regular file: {self.lock_file}")

                    # VULN-002: Reject reparse points and symlinks on Windows
                    if sys.platform.startswith("win"):
                        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                        if getattr(st, "st_file_attributes", 0) & reparse:
                            raise PermissionError(f"Security violation: lock file is a reparse point or symlink: {self.lock_file}")

                    if getattr(st, "st_nlink", 1) > 1:
                        raise PermissionError(f"Security violation: lock file has hard links: {self.lock_file}")

                    if hasattr(os, "fchmod"):
                        try:
                            os.fchmod(self.fd, 0o600)
                        except Exception:
                            pass

                    # VULN-002 / Hazard: Always write 1-byte pre-size when lock file is empty to prevent zero-length locking race
                    if st.st_size == 0:
                        try:
                            os.write(self.fd, b"\x00")
                            os.fsync(self.fd)
                        except Exception as fsync_err:
                            sys.stderr.write(f"[!] Warning: FileLock pre-size fsync failed: {fsync_err}\n")
                except (PermissionError, OSError) as open_err:
                    if self.fd is not None:
                        try:
                            os.close(self.fd)
                        except Exception:
                            pass
                        self.fd = None
                    winerror = getattr(open_err, "winerror", None)
                    e_errno = getattr(open_err, "errno", None)
                    if winerror in (32, 33):
                        if time.monotonic() >= deadline:
                            raise TimeoutError(f"Could not open lock file {self.lock_file} within {self.timeout}s: {open_err}") from open_err
                        time.sleep(0.01)
                        continue
                    # Real permission fault on os.open (EACCES / EPERM / winerror 5)
                    raise PermissionError(f"Permission denied opening lock file {self.lock_file} (errno={e_errno}, winerror={winerror}): {open_err}") from open_err

            # Step 2: Acquire OS-level advisory lock with backoff retry
            while True:
                try:
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    _lock_fd(self.fd)
                    held[self._lock_key] = 1
                    return self
                except (BlockingIOError, OSError) as lock_err:
                    winerror = getattr(lock_err, "winerror", None)
                    e_errno = getattr(lock_err, "errno", None)
                    # True contention signatures:
                    # Windows: msvcrt.locking raises OSError with errno 13 (EACCES) and no winerror, or winerror 32/33/36
                    # POSIX: EAGAIN (11), EWOULDBLOCK (11 or 35), or BlockingIOError
                    is_contention = (
                        isinstance(lock_err, BlockingIOError) or
                        (winerror in (32, 33, 36)) or
                        (e_errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, 11, 13, 35))
                    )
                    if is_contention:
                        if time.monotonic() >= deadline:
                            try:
                                os.close(self.fd)
                            except Exception:
                                pass
                            self.fd = None
                            raise TimeoutError(f"Could not acquire OS file lock on {self.lock_file} within {self.timeout}s: {lock_err}") from lock_err
                        time.sleep(0.01)
                    else:
                        try:
                            os.close(self.fd)
                        except Exception:
                            pass
                        self.fd = None
                        raise
        except Exception:
            if self._rlock is not None:
                self._rlock.release()
                _exit_process_rlock(self._lock_key)
                self._rlock = None
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        held = getattr(_lock_local, "held_locks", {})
        if self._lock_key in held:
            held[self._lock_key] -= 1
            if held[self._lock_key] > 0:
                # VULN-102: Nested exit decrements depth and releases this nesting level's RLock acquisition,
                # but preserves self._rlock and does NOT release the OS fd until the outermost exit.
                if self._rlock is not None:
                    try:
                        self._rlock.release()
                    except Exception:
                        pass
                    _exit_process_rlock(self._lock_key)
                return
            del held[self._lock_key]

        try:
            if self.fd is not None:
                try:
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    _unlock_fd(self.fd)
                except Exception:
                    pass
                try:
                    os.close(self.fd)
                except Exception:
                    pass
                self.fd = None
        finally:
            if self._rlock is not None:
                try:
                    self._rlock.release()
                except Exception:
                    pass
                _exit_process_rlock(self._lock_key)
                self._rlock = None


def _redact_trace_dict(tr: Any, depth: int = 0) -> Any:
    """Recursively redacts string values and nested structures with max depth 32 safe truncation (VULN-003, VULN-005)."""
    if depth > 32:
        return "[REDACTED_MAX_DEPTH]" 
    if isinstance(tr, dict):
        clean = {}
        for k, v in tr.items():
            if isinstance(v, str):
                try:
                    clean[k] = redact_secrets(v)
                except Exception:
                    clean[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                clean[k] = _redact_trace_dict(v, depth + 1)
            else:
                clean[k] = v
        return clean
    elif isinstance(tr, list):
        return [_redact_trace_dict(item, depth + 1) for item in tr]
    elif isinstance(tr, str):
        try:
            return redact_secrets(tr)
        except Exception:
            return "[REDACTED]"
    return tr


def _save_traces_unlocked(data: dict, path: str) -> bool:
    """Persists traces atomically using unique tempfile, fsync, replace, and chmod 0600."""
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Deep-copy and recursively redact all trace fields for persistence (VULN-002, VULN-003)
    traces = data.get("traces")
    if not isinstance(traces, list):
        raise TracePersistenceError(f"Invalid traces payload: 'traces' must be a list, got {type(traces).__name__} (VULN-002)")

    persist_traces = []
    for tr in traces:
        if isinstance(tr, dict):
            persist_traces.append(_redact_trace_dict(tr))
        else:
            raise TracePersistenceError(f"Invalid trace entry: expected dict, got {type(tr).__name__} (VULN-002)")

    if len(traces) > 0 and len(persist_traces) == 0:
        raise TracePersistenceError("persist_traces became empty while input traces was non-empty; refusing to overwrite with empty data (VULN-002)")

    persist_data = {
        "version": data.get("version", "3.0.0"),
        "updated_at": now_str,
        "traces": persist_traces
    }

    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix="traces_", suffix=".tmp")
    f = None
    try:
        f = os.fdopen(fd, "w", encoding="utf-8")
        json.dump(persist_data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
        f.close()
        f = None
        os.replace(tmp_path, path)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
        # Parent directory fsync where supported to ensure directory entry durability (Hazard 63)
        try:
            if hasattr(os, "O_DIRECTORY"):
                dir_fd = os.open(dir_name, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        except Exception:
            pass
        return True
    except Exception as e:
        sys.stderr.write(f"[!] LỖI _save_traces_unlocked({path}): {type(e).__name__}: {e}\n")
        if f is not None:
            try:
                f.close()
            except Exception:
                pass
        else:
            try:
                os.close(fd)
            except Exception:
                pass
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise TracePersistenceError(f"Failed to persist traces to {path}: {e}") from e


def save_traces(data: dict, traces_path: str = None) -> bool:
    """Persists traces atomically under OS FileLock (Hazard 4)."""
    path = traces_path or TRACES_FILE
    lock_path = path + ".lock"
    try:
        with FileLock(lock_path, timeout=5.0):
            return _save_traces_unlocked(data, path)
    except Exception as e:
        sys.stderr.write(f"[!] LỖI save_traces({path}): {type(e).__name__}: {e}\n")
        return False


def record_trace(problem_signature: str,
                 proven_solution: str,
                 action_type: str = "command",
                 tags: list = None,
                 workspace_context: str = "",
                 traces_path: str = None,
                 outbox_id: Optional[int] = None,
                 workspace_hash: Optional[str] = None,
                 outbox_generation: Optional[int] = None) -> dict:
    """
    Records or updates a proven execution trace inside a single atomic critical section.
    Supports idempotent deduplication via outbox_id + outbox_generation (VULN-004) and strict tenant isolation
    via workspace-scoped trace_id (VULN-001).
    Returns the recorded trace object or empty dict on failure.
    """
    if not problem_signature or not proven_solution:
        return {}

    path = traces_path or TRACES_FILE
    lock_path = path + ".lock"

    try:
        with FileLock(lock_path, timeout=5.0):
            try:
                data = copy.deepcopy(load_traces(path, bypass_cache=True))
            except Exception as load_err:
                sys.stderr.write(f"[!] LỖI record_trace: Aborting write to prevent data loss (load_traces failed): {load_err}\n")
                return {}
            traces = data.get("traces", [])
            
            clean_sig = redact_secrets(problem_signature) or problem_signature
            if not clean_sig or not any(c.isalnum() for c in clean_sig):
                raise ValueError("problem_signature contains no alphanumeric characters after secret redaction (Edge Case 2)")
            clean_sol = redact_secrets(proven_solution) or proven_solution
            clean_action = redact_secrets(action_type) or "command"
            clean_ctx = redact_secrets(workspace_context) or ""
            clean_tags = [redact_secrets(str(t)) for t in tags] if tags else []
            sig_tokens = tokenize(clean_sig)
            tag_tokens = []
            for t in clean_tags:
                tag_tokens.extend(tokenize(str(t)))
            all_tokens = list(set(sig_tokens + tag_tokens))

            # VULN-001: Derive trace_id with SHA-256 and workspace_hash namespace to eliminate cross-tenant collisions
            clean_ws = workspace_hash.strip().lower() if workspace_hash else ""
            if clean_ws:
                id_source = f"{clean_ws}:{clean_action}:{clean_sig.strip().lower()}"
            else:
                id_source = f"{clean_action}:{clean_sig.strip().lower()}"
            trace_id = hashlib.sha256(id_source.encode("utf-8")).hexdigest()[:24]

            # Check for existing trace STRICTLY scoped to tenant (VULN-001)
            existing = None
            for tr in traces:
                tr_ws = (tr.get("workspace_hash") or "").strip().lower()
                if clean_ws:
                    if tr_ws == clean_ws and (tr.get("id") == trace_id or tr.get("problem_signature", "").strip().lower() == clean_sig.strip().lower()):
                        existing = tr
                        break
                else:
                    if not tr_ws and (tr.get("id") == trace_id or tr.get("problem_signature", "").strip().lower() == clean_sig.strip().lower()):
                        existing = tr
                        break

            # Upgrade-in-place: If no tenant-scoped match, adopt un-scoped legacy trace with identical signature (VULN-003)
            if not existing and clean_ws:
                legacy_candidates = [
                    tr for tr in traces
                    if not (tr.get("workspace_hash") or "").strip()
                    and tr.get("problem_signature", "").strip().lower() == clean_sig.strip().lower()
                ]
                if len(legacy_candidates) == 1:
                    existing = legacy_candidates[0]
                    existing["workspace_hash"] = clean_ws

            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            if existing:
                # VULN-006: Stale outbox worker and monotonic generation fencing
                if outbox_id is not None and existing.get("last_outbox_id") == outbox_id:
                    existing_gen = existing.get("last_outbox_generation", 0)
                    if outbox_generation is None or existing_gen >= outbox_generation:
                        # Reject stale worker generation and duplicate replay without mutation
                        return copy.deepcopy(existing)

                existing["proven_solution"] = clean_sol.strip()
                existing["success_count"] = existing.get("success_count", 1) + 1
                existing["last_recalled"] = now_str
                existing["action_type"] = clean_action
                existing["tokens"] = list(set(existing.get("tokens", []) + all_tokens))
                if clean_tags:
                    existing["tags"] = list(set(existing.get("tags", []) + clean_tags))
                if clean_ctx:
                    existing["workspace_context"] = clean_ctx
                if clean_ws:
                    existing["workspace_hash"] = clean_ws
                if outbox_id is not None:
                    existing["last_outbox_id"] = outbox_id
                if outbox_generation is not None:
                    existing["last_outbox_generation"] = outbox_generation
                result_trace = existing
            else:
                new_trace = {
                    "id": trace_id,
                    "workspace_hash": clean_ws,
                    "problem_signature": clean_sig.strip(),
                    "proven_solution": clean_sol.strip(),
                    "action_type": clean_action,
                    "tags": clean_tags,
                    "workspace_context": clean_ctx,
                    "tokens": all_tokens,
                    "success_count": 1,
                    "created_at": now_str,
                    "last_recalled": now_str
                }
                if outbox_id is not None:
                    new_trace["last_outbox_id"] = outbox_id
                if outbox_generation is not None:
                    new_trace["last_outbox_generation"] = outbox_generation
                traces.append(new_trace)
                result_trace = new_trace

            # LRU Pruning if exceeds MAX_TRACES
            if len(traces) > MAX_TRACES:
                traces.sort(key=lambda x: (x.get("success_count", 1), x.get("last_recalled", "")), reverse=True)
                data["traces"] = traces[:MAX_TRACES]
            else:
                data["traces"] = traces

            ok = _save_traces_unlocked(data, path)
            if not ok:
                return {}
            try:
                stat_res = os.stat(path)
                curr_sig = (stat_res.st_mtime_ns, stat_res.st_size, getattr(stat_res, "st_ino", 0))
                with _MEM_LOCK:
                    _CACHE[os.path.abspath(path)] = {"data": copy.deepcopy(data), "sig": curr_sig}
            except Exception:
                pass
            return copy.deepcopy(_redact_trace_dict(result_trace))
    except (TimeoutError, OSError, TracePersistenceError) as infra_err:
        sys.stderr.write(f"[!] LỖI INFRASTRUCTURE record_trace: {type(infra_err).__name__}: {infra_err}\n")
        raise
    except Exception as lock_err:
        sys.stderr.write(f"[!] LỖI record_trace: {type(lock_err).__name__}: {lock_err}\n")
        return {}


def recall_traces(query_text: str,
                  workspace_dir: str = None,
                  top_k: int = 2,
                  threshold: float = 0.25,
                  traces_path: str = None,
                  workspace_hash: Optional[str] = None,
                  allow_unscoped: bool = False) -> list:
    """
    Sub-millisecond retrieval of matching proven execution traces (<0.3ms).
    Enforces strict fail-closed tenant isolation (VULN-002).
    """
    if not query_text:
        return []

    try:
        traces = _get_traces_read_view(traces_path)
    except Exception as load_err:
        sys.stderr.write(f"[!] Warning: recall_traces degraded gracefully on unreadable traces file: {load_err}\n")
        return []
    if not traces:
        return []

    query_tokens = set(tokenize(query_text))
    if not query_tokens:
        return []

    target_ws = workspace_hash.strip().lower() if workspace_hash else None
    if not target_ws and workspace_dir:
        target_ws = canonical_workspace_hash(workspace_dir)

    # Fail-closed guard: if neither workspace_hash nor workspace_dir was provided,
    # and allow_unscoped is False, deny cross-tenant trace leakage with loud diagnostic (VULN-102)
    if not target_ws and not allow_unscoped:
        from memory_utils import persist_diag
        persist_diag("recall_traces called without workspace_hash or workspace_dir and allow_unscoped=False", 256)
        sys.stderr.write("[!] Warning: recall_traces called without workspace_hash or workspace_dir (tenant isolation active, allow_unscoped=False); returning empty recall.\n")
        return []

    scored = []
    for tr in traces:
        # VULN-001, VULN-002 & VULN-003: Tenant isolation with safe null and legacy migration handling
        tr_ws = (tr.get("workspace_hash") or "").strip().lower()
        if target_ws:
            from memory_utils import legacy_workspace_hash
            leg_ws = legacy_workspace_hash(workspace_dir) if workspace_dir else None
            matches_ws = (tr_ws == target_ws) or (leg_ws and tr_ws == leg_ws)
            if not matches_ws:
                if tr_ws:
                    continue
                # If trace has no workspace_hash, permit recall if allow_unscoped or workspace_context matches
                ctx = (tr.get("workspace_context") or "").strip().lower()
                ctx_match = bool(workspace_dir and ctx and (ctx in workspace_dir.lower() or workspace_dir.lower() in ctx))
                if not (allow_unscoped or ctx_match):
                    continue

        tr_tokens = set(tr.get("tokens", []))
        if not tr_tokens:
            continue
        intersection = query_tokens.intersection(tr_tokens)
        if not intersection:
            continue

        # Jaccard + Overlap composite score
        overlap_score = len(intersection) / len(query_tokens)
        jaccard_score = len(intersection) / len(query_tokens.union(tr_tokens))
        
        # Boost for success count
        utility_boost = min(0.3, tr.get("success_count", 1) * 0.05)
        
        # Context boost if matching workspace name
        context_boost = 0.0
        if workspace_dir and tr.get("workspace_context"):
            ws_base = os.path.basename(os.path.normpath(workspace_dir)).lower()
            if ws_base in tr.get("workspace_context", "").lower():
                context_boost = 0.15

        final_score = (overlap_score * 0.6) + (jaccard_score * 0.4) + utility_boost + context_boost

        if final_score >= threshold:
            scored.append({
                "trace": copy.deepcopy(tr),
                "score": round(final_score, 3),
                "matched_tokens": list(intersection)
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    results = scored[:top_k]

    # Update last_recalled in returned view (non-mutating read path to preserve <0.3ms SLA)
    if results:
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        for res in results:
            res["trace"]["last_recalled"] = now_str

    return results


def seed_canonical_traces(traces_path: str = None):
    """Seeds baseline canonical verified engineering solutions."""
    canonical = [
        {
            "signature": "Docker port already in use / bind address in use",
            "solution": "fuser -k <port>/tcp || lsof -ti:<port> | xargs kill -9",
            "action_type": "command",
            "tags": ["docker", "port", "networking", "kill", "bind", "xung-đột-cổng", "trùng-port", "giải-phóng-port"],
            "workspace_context": "General Linux / Server"
        },
        {
            "signature": "pip install externally managed environment error on modern Linux",
            "solution": "python3 -m venv .venv && source .venv/bin/activate || pip install --break-system-packages",
            "action_type": "command",
            "tags": ["python", "pip", "venv", "externally-managed", "linux", "môi-trường-python", "lỗi-cài-pip"],
            "workspace_context": "Python / Ubuntu"
        },
        {
            "signature": "FastAPI CORS wildcard allow origins with credentials forbidden",
            "solution": "allow_origins=['http://localhost:3000'] (Explicit origins required when allow_credentials=True)",
            "action_type": "code_snippet",
            "tags": ["fastapi", "cors", "credentials", "middleware", "security", "lỗi-cors", "chặn-nguồn", "bảo-mật"],
            "workspace_context": "FastAPI / Backend"
        },
        {
            "signature": "Git push hang on Windows Credential Manager non-interactive subshell",
            "solution": "git config --global credential.helper manager && git push --dry-run",
            "action_type": "command",
            "tags": ["git", "push", "credential", "windows", "hang", "đơ-git", "xác-thực-git"],
            "workspace_context": "Git / Windows"
        },
        {
            "signature": "PowerShell command chaining syntax error with double ampersand",
            "solution": "Use semicolon ';' or separate command invocations instead of '&&' in PowerShell 5.1",
            "action_type": "command",
            "tags": ["powershell", "syntax", "chaining", "windows", "cú-pháp-powershell", "nối-lệnh"],
            "workspace_context": "PowerShell / Windows"
        }
    ]
    for item in canonical:
        record_trace(
            problem_signature=item["signature"],
            proven_solution=item["solution"],
            action_type=item["action_type"],
            tags=item["tags"],
            workspace_context=item["workspace_context"],
            traces_path=traces_path
        )
    return len(canonical)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Omni-Kernel Experiential Memory Engine CLI")
    parser.add_argument("--list", action="store_true", help="List all stored proven execution traces")
    parser.add_argument("--query", "-q", type=str, default="", help="Query matching execution traces")
    parser.add_argument("--seed", action="store_true", help="Seed baseline canonical traces")
    parser.add_argument("--record", action="store_true", help="Record a new execution trace")
    parser.add_argument("--signature", "-s", type=str, default="", help="Problem signature")
    parser.add_argument("--solution", "-sol", type=str, default="", help="Proven working solution")
    parser.add_argument("--tags", "-t", type=str, default="", help="Comma-separated tags")
    parser.add_argument("--context", "-c", type=str, default="", help="Workspace context")
    args = parser.parse_args()

    if args.seed:
        seed_canonical_traces()
        print("✅ Baseline canonical execution traces seeded successfully.")
        sys.exit(0)

    if args.record:
        if not args.signature or not args.solution:
            print("❌ Both --signature and --solution are required to record a trace.")
            sys.exit(1)
        tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
        tr = record_trace(args.signature, args.solution, tags=tag_list, workspace_context=args.context)
        print(f"✅ Recorded execution trace '{tr.get('id')}': {tr.get('problem_signature')}")
        sys.exit(0)

    if args.query:
        matches = recall_traces(args.query)
        if not matches:
            print(f"ℹ️ No proven execution traces matched '{args.query}'.")
        else:
            print(f"💡 Found {len(matches)} matching proven execution trace(s):\n" + "=" * 60)
            for i, m in enumerate(matches, 1):
                tr = m["trace"]
                print(f"[{i}] Match Score: {m['score']*100:.1f}% (Matched: {', '.join(m['matched_tokens'])})")
                print(f"    Problem:  {tr['problem_signature']}")
                print(f"    Solution: {tr['proven_solution']}")
                print(f"    Context:  {tr['workspace_context']} | Successes: {tr['success_count']}\n")
        sys.exit(0)

    # Default: list traces
    data = load_traces()
    traces = data.get("traces", [])
    print("🧠 OMNI-KERNEL EXPERIENTIAL MEMORY LEDGER\n" + "=" * 65)
    print(f"Total Proven Traces: {len(traces)} | Last Updated: {data.get('updated_at', 'Never')}\n")
    if not traces:
        print("No traces stored. Run with --seed to populate initial canonical fixes.")
    else:
        for i, tr in enumerate(traces, 1):
            print(f"[{i}] {tr['id']}: {tr['problem_signature']}")
            print(f"    💡 Solution: {tr['proven_solution']}")
            print(f"    🏷️  Tags: {', '.join(tr.get('tags', []))} | Used: {tr.get('success_count', 1)} times\n")


if __name__ == "__main__":
    main()
