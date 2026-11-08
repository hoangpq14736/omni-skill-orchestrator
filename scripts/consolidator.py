"""
Tier 3 Background Memory Consolidator for Omni-Memory v4.1.
Operates out-of-band to cluster activation logs, promote proven patterns with bilingual tags,
apply bounded Ebbinghaus decay, manage soft-archiving, and perform WAL maintenance.
100% Python Standard Library.
"""

import argparse
import datetime
import errno
import hashlib
import json
import math
import uuid
import os
import sqlite3
import sys
import time
import unicodedata
from typing import Dict, List, Optional, Tuple, Any

# Ensure scripts directory is on sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_utils import fold_vietnamese, canonical_workspace_hash, redact_secrets, is_valid_hex_hash, persist_diag
from memory_schema import init_database
from experiential_memory import record_trace, TRACES_FILE, TracePersistenceError
from workspace_sanitizer import TrustFileLock

# is_valid_hex_hash imported directly from memory_utils (Directive 8)


def resolve_workspace_hash(ws_dir: Any, approved_root: Optional[str] = None, allow_unscoped: bool = False, authorized_hashes: Optional[Any] = None) -> str:
    """
    Validate and resolve workspace hash by canonicalizing directory path and
    enforcing containment within approved_root. If input is already a valid 32-hex hash
    from staging log, validates against approved_root or requires allow_unscoped=True (VULN-007).
    """
    if not isinstance(ws_dir, str) or not ws_dir.strip():
        raise ValueError("Invalid workspace directory: must be non-empty string")
    cleaned = ws_dir.strip()
    if len(cleaned) > 4096:
        raise ValueError("Workspace path exceeds maximum 4096 characters")
    if "\x00" in cleaned:
        raise ValueError("Workspace path contains invalid null byte")

    # If already a valid hexadecimal hash (supports both 64-hex SHA-256 and legacy 32-hex MD5) (VULN-001)
    if is_valid_hex_hash(cleaned, length=None):
        cleaned_lower = cleaned.lower()
        if authorized_hashes is not None and cleaned_lower in {str(h).lower() for h in authorized_hashes if h}:
            return cleaned_lower
        if approved_root is not None:
            if not isinstance(approved_root, str) or not approved_root.strip():
                raise ValueError("approved_root is configured but empty or invalid")
            canon_root_sha = canonical_workspace_hash(approved_root).lower()
            canon_root_md5 = hashlib.md5(os.path.normcase(os.path.realpath(os.path.abspath(unicodedata.normalize("NFC", str(approved_root))))).encode("utf-8")).hexdigest().lower()
            if cleaned_lower in (canon_root_sha, canon_root_md5):
                return cleaned_lower
            if allow_unscoped:
                return cleaned_lower
            raise ValueError(f"Workspace hash {cleaned_lower} is not authorized under approved root")
        if not allow_unscoped:
            raise ValueError("approved_root is required for workspace isolation; pass allow_unscoped=True to bypass intentionally")
        return cleaned_lower

    if approved_root is None:
        if not allow_unscoped:
            raise ValueError("approved_root is required for workspace isolation; pass allow_unscoped=True to bypass intentionally")
        return canonical_workspace_hash(os.path.realpath(os.path.abspath(cleaned)))

    real_path = os.path.realpath(os.path.abspath(cleaned))
    canon_root = os.path.realpath(os.path.abspath(approved_root.strip()))
    norm_root = os.path.normcase(os.path.normpath(canon_root))
    norm_target = os.path.normcase(os.path.normpath(real_path))
    try:
        common = os.path.commonpath([norm_root, norm_target])
        if common != norm_root:
            raise ValueError("Workspace path escapes approved root")
    except ValueError:
        raise ValueError("Workspace path is outside approved root")
    return canonical_workspace_hash(real_path)


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
def _chunked_execute(cur: sqlite3.Cursor, query_template: str, ids: List[Any], chunk_size: int = 500, prefix_params: Tuple = ()):
    """Execute SQL IN (...) queries in safe chunks to prevent exceeding SQLITE_MAX_VARIABLE_NUMBER (VULN-010)."""
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i:i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        cur.execute(query_template.format(placeholders=placeholders), list(prefix_params) + chunk)


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


def safe_err(exc: Any) -> str:
    """Safely redact secrets from exception messages before logging or returning (VULN-006, VULN-002)."""
    return persist_diag(exc, max_len=512)


def is_transient_io_error(err: Any, visited: Optional[set] = None, depth: int = 0) -> bool:
    """
    Classify whether an I/O error is transient (lock contention, busy, timeout)
    versus permanent (PermissionError, FileNotFoundError, ENOSPC, EROFS, etc.) (VULN-006).
    Recursively inspects __cause__ chain with cycle protection and bounded depth (VULN-002).
    """
    if err is None or depth > 16:
        return False

    if visited is None:
        visited = set()
    err_id = id(err)
    if err_id in visited:
        return False
    visited.add(err_id)

    if hasattr(err, "__cause__") and err.__cause__ is not None:
        if is_transient_io_error(err.__cause__, visited=visited, depth=depth + 1):
            return True

    if isinstance(err, TimeoutError):
        return True

    # Check Windows winerror FIRST, because Python maps ERROR_SHARING_VIOLATION (32)
    # and ERROR_LOCK_VIOLATION (33) to PermissionError (winerror=32/33, errno=13).
    winerror = getattr(err, "winerror", None)
    if winerror is not None:
        if winerror in (32, 33):  # ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION
            return True
        if winerror in (2, 3, 5, 112):  # FILE_NOT_FOUND, PATH_NOT_FOUND, ACCESS_DENIED, DISK_FULL
            return False

    if isinstance(err, (PermissionError, FileNotFoundError, IsADirectoryError)):
        return False

    if isinstance(err, OSError):
        permanent_errnos = {
            getattr(errno, "EACCES", 13),
            getattr(errno, "EPERM", 1),
            getattr(errno, "ENOENT", 2),
            getattr(errno, "ENOSPC", 28),
            getattr(errno, "EROFS", 30),
            getattr(errno, "EISDIR", 21),
            getattr(errno, "ENAMETOOLONG", 36),
            getattr(errno, "EFBIG", 27),
        }
        if getattr(err, "errno", None) in permanent_errnos:
            return False

        transient_errnos = {
            getattr(errno, "EAGAIN", 11),
            getattr(errno, "EWOULDBLOCK", 11),
            getattr(errno, "ETIMEDOUT", 110),
            getattr(errno, "EBUSY", 16),
        }
        if getattr(err, "errno", None) in transient_errnos:
            return True

    return False


def flush_outbox(conn: sqlite3.Connection, limit: int = 50, workspace_hash: Optional[str] = None) -> int:
    """
    Drains pending records from consolidation_outbox into proven_traces.json with atomic InFlight claim.
    Two-phase transaction:
    Phase 1: Claim rows atomically with unique owner_token & claimed_at timestamp, and commit immediately (VULN-001, Hazard 43).
    Phase 2: Perform file I/O (record_trace) outside of SQLite transaction to prevent blocking writers (VULN-003).
    Phase 3: Short atomic transaction to update row statuses (Flushed / Failed / Pending) using CAS on owner_token.
    """
    # VULN-001: Guard in_transaction FIRST before any other logic; NEVER mutate conn.isolation_level
    if getattr(conn, "in_transaction", False):
        raise RuntimeError("flush_outbox must be called outside active transactions to prevent holding write locks across file I/O (Hazard 42)")

    if not (1 <= limit <= 500):
        raise ValueError(f"limit must be between 1 and 500, got {limit}")

    if workspace_hash is not None:
        clean_ws = workspace_hash.strip().lower()
        if not clean_ws:
            raise ValueError("workspace_hash cannot be empty or whitespace string; pass None for intentional unscoped flush")
        if not is_valid_hex_hash(clean_ws):
            raise ValueError(f"workspace_hash must be a 32-hex character string, got: '{workspace_hash}'")
    else:
        clean_ws = None

    cur = conn.cursor()
    use_savepoint = conn.isolation_level is not None
    sp_claim = f"sp_claim_{uuid.uuid4().hex[:12]}"
    if use_savepoint:
        conn.execute(f"SAVEPOINT {sp_claim};")
    else:
        conn.execute("BEGIN IMMEDIATE;")
    owner_token = uuid.uuid4().hex

    try:
        # Reset any stale InFlight rows (>180s old or legacy NULL claimed_at) back to Pending or Failed after max retries (Hazard 38)
        cur.execute(
            """
            UPDATE consolidation_outbox
            SET status = CASE WHEN retry_count + 1 >= 5 THEN 'Failed' ELSE 'Pending' END,
                retry_count = retry_count + 1,
                last_error = 'Claim lease expired (stale worker)',
                owner_token = NULL,
                claimed_at = NULL
            WHERE status = 'InFlight' AND (claimed_at IS NULL OR claimed_at < datetime('now', '-180 seconds'))
              AND (? IS NULL OR workspace_hash = ?);
            """,
            (clean_ws, clean_ws)
        )

        # Select pending rows to claim scoped by workspace_hash (VULN-005)
        cur.execute(
            """
            SELECT outbox_id, signature, solution, tags, context, retry_count, memory_id, workspace_hash, COALESCE(generation, 1)
            FROM consolidation_outbox
            WHERE status = 'Pending' AND (? IS NULL OR workspace_hash = ?)
            ORDER BY outbox_id ASC
            LIMIT ?;
            """,
            (clean_ws, clean_ws, limit)
        )
        pending = cur.fetchall()
        if not pending:
            if use_savepoint:
                conn.execute(f"RELEASE SAVEPOINT {sp_claim};")
            else:
                conn.commit()
            return 0

        # Atomically claim rows as InFlight with timestamp and owner token (CAS lease)
        claimed_ids = [r[0] for r in pending]
        _chunked_execute(
            cur,
            "UPDATE consolidation_outbox SET status = 'InFlight', claimed_at = datetime('now'), owner_token = ? WHERE outbox_id IN ({placeholders});",
            claimed_ids,
            prefix_params=(owner_token,)
        )
        if use_savepoint:
            conn.execute(f"RELEASE SAVEPOINT {sp_claim};")
        else:
            conn.commit()
    except Exception as claim_err:
        try:
            if use_savepoint:
                conn.execute(f"ROLLBACK TO SAVEPOINT {sp_claim};")
                conn.execute(f"RELEASE SAVEPOINT {sp_claim};")
            else:
                conn.rollback()
        except Exception as rb_err:
            persist_diag(rb_err, 256)
            sys.stderr.write(f"[!] Warning: flush_outbox claim rollback failed: {rb_err}\n")
        sys.stderr.write(f"[!] Warning: flush_outbox claim failed: {type(claim_err).__name__}: {claim_err}\n")
        # VULN-005: Never silently swallow claim failure as 0 flushed
        raise RuntimeError(f"flush_outbox claim phase failed: {claim_err}") from claim_err

    # Phase 2: Execute File I/O completely outside SQLite transaction (VULN-003)
    results = []
    for row in pending:
        ob_id, sig, sol, tags_json, ctx, retries, mem_id, ws_hash, ob_gen = row
        try:
            # VULN-001: parse tags defensively and ensure list type
            tags = json.loads(tags_json) if tags_json else []
            if not isinstance(tags, list):
                tags = [str(tags)]
        except Exception as je:
            results.append((ob_id, False, f"JSONDecodeError in tags: {je}", retries, ob_gen, False))
            continue

        try:
            res = record_trace(
                problem_signature=sig,
                proven_solution=sol,
                tags=tags,
                workspace_context=ctx,
                outbox_id=ob_id,
                workspace_hash=ws_hash,
                outbox_generation=ob_gen
            )
            if not res or not isinstance(res, dict) or not res.get("id"):
                raise RuntimeError(f"record_trace failed to persist trace for outbox {ob_id} (mem_id={mem_id})")
            results.append((ob_id, True, None, retries, ob_gen, False))
        except Exception as ob_err:
            # VULN-006: Strictly classify transient lock contention vs permanent errors via errno/winerror
            is_transient = is_transient_io_error(ob_err)
            results.append((ob_id, False, f"{type(ob_err).__name__}: {ob_err}", retries, ob_gen, is_transient))

    # Phase 3: Short atomic update transaction using CAS on owner_token, status='InFlight', and generation (VULN-005)
    flushed_count = 0
    if results:
        sp_status = f"sp_status_{uuid.uuid4().hex[:12]}"
        if use_savepoint:
            conn.execute(f"SAVEPOINT {sp_status};")
        else:
            conn.execute("BEGIN IMMEDIATE;")
        try:
            for ob_id, is_success, err_msg, retries, ob_gen, is_transient in results:
                redacted_err = safe_err(err_msg) if err_msg else None

                if is_success:
                    cur.execute(
                        """
                        UPDATE consolidation_outbox
                        SET status = 'Flushed', flushed_at = datetime('now')
                        WHERE outbox_id = ? AND owner_token = ? AND status = 'InFlight' AND COALESCE(generation, 1) = ?;
                        """,
                        (ob_id, owner_token, ob_gen)
                    )
                    if cur.rowcount > 0:
                        flushed_count += 1
                else:
                    # VULN-006: Bounded retry counter: transient fails after 10 attempts, permanent fails after 5
                    new_retries = retries + 1
                    max_retries = 10 if is_transient else 5
                    new_status = 'Failed' if new_retries >= max_retries else 'Pending'
                    err_prefix = "Transient IO/Lock: " if is_transient else ""
                    full_err_diag = f"{err_prefix}{redacted_err}"
                    cur.execute(
                        """
                        UPDATE consolidation_outbox
                        SET retry_count = ?, status = ?, last_error = ?, owner_token = NULL, claimed_at = NULL
                        WHERE outbox_id = ? AND owner_token = ? AND status = 'InFlight' AND COALESCE(generation, 1) = ?;
                        """,
                        (new_retries, new_status, full_err_diag, ob_id, owner_token, ob_gen)
                    )
                    if new_status == 'Failed':
                        sys.stderr.write(f"[!] FATAL: Outbox record {ob_id} permanently failed: {full_err_diag}\n")
            if use_savepoint:
                conn.execute(f"RELEASE SAVEPOINT {sp_status};")
            else:
                conn.commit()
        except Exception as tx_err:
            if use_savepoint:
                try:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp_status};")
                    conn.execute(f"RELEASE SAVEPOINT {sp_status};")
                except Exception:
                    pass
            else:
                try:
                    conn.rollback()
                except Exception:
                    pass
            sys.stderr.write(f"[!] FATAL: flush_outbox status update transaction failed: {safe_err(tx_err)}\n")
            raise RuntimeError(f"flush_outbox status update phase failed: {tx_err}") from tx_err

    return flushed_count


# ----------------------------------------------------------------------
# Tier 3 Consolidator Engine Core
# ----------------------------------------------------------------------
class ConsolidatorEngine:
    """Consolidation pipeline processor."""

    def __init__(self, db_conn: sqlite3.Connection, workspace_root: Optional[str] = None, workspace_hash: Optional[str] = None, allow_unscoped: bool = False):
        self.conn = db_conn
        # VULN-001: Guard in_transaction; NEVER mutate self.conn.isolation_level
        if getattr(self.conn, "in_transaction", False):
            raise RuntimeError("ConsolidatorEngine cannot be initialized while an uncommitted transaction is active on the connection")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.workspace_root = workspace_root
        self.allow_unscoped = allow_unscoped
        self.authorized_hashes = set()
        if self.workspace_root:
            root_hash = canonical_workspace_hash(self.workspace_root)
            self.authorized_hashes.add(root_hash)
            try:
                c = self.conn.cursor()
                c.execute("SELECT DISTINCT workspace_path FROM workspace_episodic_memory WHERE workspace_path IS NOT NULL;")
                norm_root = os.path.normcase(os.path.normpath(os.path.realpath(os.path.abspath(self.workspace_root))))
                for (r_path,) in c.fetchall():
                    if r_path and not is_valid_hex_hash(r_path):
                        try:
                            norm_target = os.path.normcase(os.path.normpath(os.path.realpath(os.path.abspath(r_path))))
                            if os.path.commonpath([norm_root, norm_target]) == norm_root:
                                computed_h = canonical_workspace_hash(r_path)
                                self.authorized_hashes.add(computed_h.lower())
                        except Exception:
                            pass
            except Exception as db_err:
                sys.stderr.write(f"[!] Warning: Failed to initialize authorized_hashes from DB: {db_err}\n")
        elif self.allow_unscoped:
            try:
                c = self.conn.cursor()
                c.execute("SELECT DISTINCT workspace_hash FROM workspace_episodic_memory WHERE workspace_hash IS NOT NULL;")
                for (r_hash,) in c.fetchall():
                    if r_hash and is_valid_hex_hash(r_hash):
                        self.authorized_hashes.add(r_hash.lower())
            except Exception as db_err:
                sys.stderr.write(f"[!] Warning: Failed to initialize authorized_hashes from DB: {db_err}\n")

        # Sync authorized hashes from persistent workspace_registry table (VULN-007)
        try:
            c = self.conn.cursor()
            c.execute("SELECT workspace_hash, workspace_path FROM workspace_registry;")
            for r_hash, r_path in c.fetchall():
                if r_hash:
                    if self.workspace_root:
                        try:
                            norm_root = os.path.normcase(os.path.normpath(os.path.realpath(os.path.abspath(self.workspace_root))))
                            norm_target = os.path.normcase(os.path.normpath(os.path.realpath(os.path.abspath(r_path))))
                            if os.path.commonpath([norm_root, norm_target]) == norm_root:
                                self.authorized_hashes.add(r_hash.lower())
                        except Exception:
                            pass
                    else:
                        self.authorized_hashes.add(r_hash.lower())

            # VULN-106: Reconcile unconsolidated legacy 32-hex subfolder partitions belonging to workspace_root tree
            if self.workspace_root:
                canon_root_md5 = hashlib.md5(os.path.normcase(os.path.realpath(os.path.abspath(unicodedata.normalize("NFC", str(self.workspace_root))))).encode("utf-8")).hexdigest().lower()
                self.authorized_hashes.add(canon_root_md5)
                c.execute("SELECT DISTINCT workspace_dir FROM activation_events WHERE is_consolidated = 0 AND length(workspace_dir) = 32;")
                norm_root = os.path.normcase(os.path.normpath(os.path.realpath(os.path.abspath(self.workspace_root))))
                for (uncons_h,) in c.fetchall():
                    if uncons_h and uncons_h.lower() not in self.authorized_hashes:
                        reg_match = c.execute("SELECT workspace_path FROM workspace_registry WHERE lower(workspace_hash) = ?;", (uncons_h.lower(),)).fetchone()
                        if reg_match and reg_match[0]:
                            try:
                                norm_cand = os.path.normcase(os.path.normpath(os.path.realpath(os.path.abspath(reg_match[0]))))
                                if os.path.commonpath([norm_root, norm_cand]) == norm_root:
                                    self.authorized_hashes.add(uncons_h.lower())
                            except Exception:
                                pass
        except Exception as reg_err:
            persist_diag(reg_err, 256)
            sys.stderr.write(f"[!] Warning: Failed to sync authorized_hashes from workspace_registry: {reg_err}\n")

        if workspace_hash is not None:
            if not is_valid_hex_hash(workspace_hash):
                raise ValueError(f"Invalid workspace_hash: {workspace_hash!r}")
            clean_supplied = workspace_hash.strip().lower()
            if self.workspace_root and clean_supplied not in self.authorized_hashes:
                raise ValueError(f"workspace_hash '{clean_supplied}' does not belong to approved workspace_root '{self.workspace_root}'")
            self.workspace_hash = clean_supplied
            self.authorized_hashes.add(clean_supplied)
        elif self.workspace_root is not None:
            self.workspace_hash = canonical_workspace_hash(self.workspace_root)
        else:
            self.workspace_hash = None

    def register_workspace(self, workspace_path: str) -> str:
        """Registers and authorizes a sub-workspace within workspace_root and persists to workspace_registry (VULN-003, VULN-007)."""
        h = resolve_workspace_hash(workspace_path, approved_root=self.workspace_root, allow_unscoped=self.allow_unscoped)
        self.authorized_hashes.add(h)
        try:
            now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            self.conn.execute(
                "INSERT OR REPLACE INTO workspace_registry (workspace_hash, workspace_path, registered_at) VALUES (?, ?, ?)",
                (h, str(workspace_path), now_iso)
            )
            self.conn.commit()
        except Exception as reg_err:
            sys.stderr.write(f"[!] Warning: Failed to persist workspace_registry for {h}: {reg_err}\n")
        return h

    def drain_l1_staging(self, chunk_size: int = 100, dry_run: bool = False) -> int:
        """
        Drain events from l1_staging_log into activation_events table atomically.
        Acquires immediate write lock prior to SELECT to eliminate TOCTOU duplicate drain races.
        """
        if not (1 <= chunk_size <= 10000):
            raise ValueError(f"chunk_size must be between 1 and 10000, got {chunk_size}")

        if not self.workspace_hash and not self.allow_unscoped:
            raise RuntimeError("drain_l1_staging cannot operate on unscoped engine when allow_unscoped=False (VULN-003)")

        cur = self.conn.cursor()

        # In dry_run mode, perform strictly read-only query using subquery COUNT
        if dry_run:
            if self.workspace_hash:
                cur.execute(
                    "SELECT COUNT(*) FROM (SELECT 1 FROM l1_staging_log WHERE is_drained = 0 AND workspace_hash = ? LIMIT ?);",
                    (self.workspace_hash, chunk_size)
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) FROM (SELECT 1 FROM l1_staging_log WHERE is_drained = 0 LIMIT ?);",
                    (chunk_size,)
                )
            row = cur.fetchone()
            return row[0] if row else 0

        # Phase 1: Read and parse offline spool OUTSIDE of SQLite write transaction (VULN-005)
        spool_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "l1_staging_spool.jsonl")
        spool_lock = spool_path + ".lock"

        # VULN-103 & VULN-102: Crash-recovery sweep for orphaned .proc_* files left by previous crashed drains
        spool_dir = os.path.dirname(spool_path)
        base_name = os.path.basename(spool_path)
        try:
            for fname in os.listdir(spool_dir):
                if fname.startswith(base_name + ".proc_"):
                    stale_proc = os.path.join(spool_dir, fname)
                    try:
                        if os.path.isfile(stale_proc) and os.path.getsize(stale_proc) > 0:
                            recovered_tmp = f"{stale_proc}.rec_{uuid.uuid4().hex[:6]}"
                            os.replace(stale_proc, recovered_tmp)
                            with TrustFileLock(spool_lock, timeout=2.0):
                                with open(recovered_tmp, "r", encoding="utf-8") as rf, open(spool_path, "a", encoding="utf-8") as wf:
                                    wf.write(rf.read())
                            os.remove(recovered_tmp)
                            persist_diag(f"Recovered orphaned spool file {fname} into live spool", 256)
                    except Exception as rec_err:
                        persist_diag(rec_err, 256)
        except Exception as scan_err:
            persist_diag(scan_err, 256)

        proc_path = spool_path + f".proc_{os.getpid()}_{uuid.uuid4().hex[:6]}"
        spool_staged = False

        if os.path.exists(spool_path):
            try:
                with TrustFileLock(spool_lock, timeout=2.0):
                    if os.path.exists(spool_path) and os.path.getsize(spool_path) > 0:
                        os.replace(spool_path, proc_path)
                        spool_staged = True
            except Exception as lk_err:
                persist_diag(lk_err, 256)

        parsed_spool_rows = []
        if spool_staged and os.path.exists(proc_path):
            bad_lines = []
            lines_read = 0
            try:
                with open(proc_path, "r", encoding="utf-8") as sf:
                    for line in sf:
                        lines_read += 1
                        if lines_read > 5000:
                            break
                        line_s = line.strip()
                        if not line_s:
                            continue
                        try:
                            s_data = json.loads(line_s)
                            parsed_spool_rows.append((
                                s_data.get("session_id", "session_default"),
                                s_data.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                                s_data.get("user_input", "")[:250],
                                s_data.get("workspace_hash", ""),
                                s_data.get("top_skill", "none"),
                                s_data.get("tier_used", 1),
                                json.dumps(s_data.get("recalled_traces", []))
                            ))
                        except Exception as parse_err:
                            persist_diag(parse_err, 256)
                            bad_lines.append((line_s, str(parse_err)))

                if bad_lines:
                    bad_path = spool_path + ".bad.jsonl"
                    with open(bad_path, "a", encoding="utf-8") as bf:
                        for b_line, b_err in bad_lines:
                            bf.write(json.dumps({"line": b_line, "error": b_err}, ensure_ascii=False) + "\n")
            except Exception as spool_drain_err:
                persist_diag(spool_drain_err, 256)

        # Phase 2: Open SQLite transaction strictly for fast in-memory DB operations
        own_tx = not getattr(self.conn, "in_transaction", False)
        sp_drain = f"sp_drain_{uuid.uuid4().hex[:12]}"

        if own_tx:
            self.conn.execute("BEGIN IMMEDIATE;")
        else:
            self.conn.execute(f"SAVEPOINT {sp_drain};")

        try:
            if parsed_spool_rows:
                cur.executemany(
                    """
                    INSERT OR IGNORE INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash, top_skill, tier_used, recalled_traces)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    parsed_spool_rows
                )

            if self.workspace_hash:
                cur.execute(
                    """
                    SELECT staging_id, session_id, timestamp, user_input, workspace_hash, top_skill, tier_used, recalled_traces
                    FROM l1_staging_log
                    WHERE is_drained = 0 AND workspace_hash = ?
                    ORDER BY staging_id ASC
                    LIMIT ?;
                    """,
                    (self.workspace_hash, chunk_size)
                )
            else:
                cur.execute(
                    """
                    SELECT staging_id, session_id, timestamp, user_input, workspace_hash, top_skill, tier_used, recalled_traces
                    FROM l1_staging_log
                    WHERE is_drained = 0
                    ORDER BY staging_id ASC
                    LIMIT ?;
                    """,
                    (chunk_size,)
                )
            rows = cur.fetchall()
            if not rows:
                if own_tx:
                    self.conn.commit()
                else:
                    self.conn.execute(f"RELEASE SAVEPOINT {sp_drain};")
                return 0

            drained_ids = []
            quarantined_ids = []
            for row in rows:
                s_id, session_id, ts, u_input, ws_hash, top_skill, tier, recalled = row
                try:
                    safe_input = str(redact_secrets(u_input) or "")
                    safe_skill = str(redact_secrets(top_skill)) if top_skill else None
                    raw_recalled = redact_secrets(recalled) if recalled else None
                    safe_recalled = json.dumps(raw_recalled, ensure_ascii=False) if isinstance(raw_recalled, (dict, list)) else (str(raw_recalled) if raw_recalled is not None else None)
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO activation_events (session_id, timestamp, user_input, workspace_dir, top_skill, tier_used, recalled_traces, feedback_score, is_consolidated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0)
                        """,
                        (session_id, ts, safe_input, ws_hash, safe_skill, tier, safe_recalled)
                    )
                    drained_ids.append(s_id)
                except Exception as row_err:
                    diag = persist_diag(row_err)
                    sys.stderr.write(f"[!] Warning: Quarantining poison pill staging row {s_id}: {diag}\n")
                    quarantined_ids.append((s_id, diag))

            if drained_ids:
                _chunked_execute(cur, "UPDATE l1_staging_log SET is_drained = 1 WHERE staging_id IN ({placeholders})", drained_ids)
                _chunked_execute(cur, "DELETE FROM l1_staging_log WHERE staging_id IN ({placeholders})", drained_ids)
            if quarantined_ids:
                for q_id, q_err in quarantined_ids:
                    cur.execute("UPDATE l1_staging_log SET is_drained = 2, last_error = ? WHERE staging_id = ?", (q_err, q_id))

            if own_tx:
                self.conn.commit()
            else:
                self.conn.execute(f"RELEASE SAVEPOINT {sp_drain};")

            # Remove processed spool file only after successful transaction commit (VULN-001)
            if spool_staged and os.path.exists(proc_path):
                try:
                    os.remove(proc_path)
                except Exception:
                    pass
            return len(drained_ids)
        except Exception:
            if own_tx:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            else:
                try:
                    self.conn.execute(f"ROLLBACK TO SAVEPOINT {sp_drain};")
                    self.conn.execute(f"RELEASE SAVEPOINT {sp_drain};")
                except Exception:
                    pass
            # Restore unprocessed spool file on rollback so no telemetry is lost (VULN-001)
            if spool_staged and os.path.exists(proc_path):
                try:
                    with TrustFileLock(spool_lock, timeout=2.0):
                        with open(proc_path, "r", encoding="utf-8") as src, open(spool_path, "a", encoding="utf-8") as dst:
                            dst.write(src.read())
                    os.remove(proc_path)
                except Exception:
                    pass
            raise

    def consolidate_batch(self, batch_size: int = 100, dry_run: bool = False, allow_unscoped: Optional[bool] = None) -> Dict[str, Any]:
        """
        Execute full consolidation cycle atomically:
        1. Drain pending L1 logs.
        2. Ingest unprocessed activation events inside single serialized IMMEDIATE transaction.
        3. Cluster patterns by folded signature.
        4. Promote patterns with >= 2 successes.
        5. Apply Ebbinghaus decay and soft-archive stale records (strictly workspace-scoped, VULN-001).
        6. Mark events as consolidated or quarantined (is_consolidated: 0=pending, 1=done, 2=quarantined).
        """
        if not (1 <= batch_size <= 10000):
            raise ValueError(f"batch_size must be between 1 and 10000, got {batch_size}")
        if allow_unscoped is True and not self.allow_unscoped:
            raise RuntimeError("Cannot override allow_unscoped=True when ConsolidatorEngine was constructed with allow_unscoped=False (VULN-009)")
        effective_unscoped = self.allow_unscoped if allow_unscoped is None else (self.allow_unscoped and allow_unscoped)
        cur = self.conn.cursor()

        # VULN-002 & VULN-003: Fail-loud gate when unscoped and allow_unscoped=False
        if not self.workspace_hash and not effective_unscoped:
            sys.stderr.write("[!] LỖI VẬN HÀNH: Skipping unscoped consolidation cycle (unconfigured workspace)\n")
            return {
                "status": "unconfigured_unscoped_error",
                "events_processed": 0,
                "promoted_traces": 0,
                "soft_archived": 0
            }

        # Step 1: Drain any pending L1 logs atomically
        self.drain_l1_staging(chunk_size=batch_size, dry_run=dry_run)

        # Strictly Zero-Mutation Preview for dry_run - executed without write locks (VULN-004)
        if dry_run:
            if self.workspace_hash:
                from memory_utils import legacy_workspace_hash
                target_path = self.workspace_root
                if not target_path:
                    row_path = cur.execute("SELECT workspace_path FROM workspace_registry WHERE workspace_hash = ? LIMIT 1;", (self.workspace_hash,)).fetchone()
                    if row_path and row_path[0]:
                        target_path = row_path[0]
                leg_h = legacy_workspace_hash(target_path) if target_path else self.workspace_hash
                match_hashes = set(self.authorized_hashes) if self.authorized_hashes else set()
                match_hashes.add(self.workspace_hash)
                if target_path:
                    match_hashes.add(target_path)
                if leg_h:
                    match_hashes.add(leg_h)
                query_hashes = [h for h in match_hashes if h and len(str(h)) <= 4096][:900]
                placeholders = ",".join("?" for _ in query_hashes)
                cur.execute(
                    f"""
                    SELECT event_id, session_id, timestamp, user_input, workspace_dir, feedback_score
                    FROM activation_events
                    WHERE is_consolidated = 0 AND workspace_dir IN ({placeholders})
                    ORDER BY event_id ASC
                    LIMIT ?;
                    """,
                    (*query_hashes, batch_size)
                )
            else:
                cur.execute(
                    """
                    SELECT event_id, session_id, timestamp, user_input, workspace_dir, feedback_score
                    FROM activation_events
                    WHERE is_consolidated = 0
                    ORDER BY event_id ASC
                    LIMIT ?;
                    """,
                    (batch_size,)
                )
            events = cur.fetchall()
            clusters: Dict[str, List[Dict[str, Any]]] = {}
            processed_count = 0
            for ev in events:
                ev_id, sess_id, ts, user_inp, ws_dir, fb = ev
                if not user_inp or fb < 0.0:
                    processed_count += 1
                    continue
                try:
                    ws_hash = resolve_workspace_hash(ws_dir, approved_root=self.workspace_root, allow_unscoped=(self.workspace_root is None or self.allow_unscoped), authorized_hashes=self.authorized_hashes)
                except Exception as d_err:
                    sys.stderr.write(f"[!] Warning: dry_run resolve_workspace_hash failed for event {ev_id}: {d_err}\n")
                    continue
                norm_query = fold_vietnamese(user_inp.strip())
                clusters.setdefault(f"{ws_hash}::{norm_query}", []).append({"feedback": fb})
                processed_count += 1

            prospective_promotions = sum(
                1 for c in clusters.values() if len([e for e in c if e.get("feedback", 0.0) > 0.0]) >= 2
            )
            if self.workspace_hash:
                cur.execute(
                    """
                    SELECT count(*) FROM workspace_episodic_memory
                    WHERE confidence_score < 0.20
                      AND status = 'Active'
                      AND memory_type != 'invariant'
                      AND COALESCE(last_accessed_at, created_at) < datetime('now', '-7 days')
                      AND workspace_hash = ?;
                    """,
                    (self.workspace_hash,)
                )
            elif effective_unscoped:
                cur.execute(
                    """
                    SELECT count(*) FROM workspace_episodic_memory
                    WHERE confidence_score < 0.20
                      AND status = 'Active'
                      AND memory_type != 'invariant'
                      AND COALESCE(last_accessed_at, created_at) < datetime('now', '-7 days');
                    """
                )
            else:
                cur.execute("SELECT 0;")
            prospective_archived = cur.fetchone()[0]
            return {
                "events_processed": processed_count,
                "promoted_traces": prospective_promotions,
                "soft_archived": prospective_archived
            }

        # Open serialized transaction BEFORE SELECT to eliminate multi-process TOCTOU races
        own_tx = not getattr(self.conn, "in_transaction", False)
        sp_name = f"sp_cons_{uuid.uuid4().hex[:12]}"
        if own_tx:
            self.conn.execute("BEGIN IMMEDIATE;")
        else:
            self.conn.execute(f"SAVEPOINT {sp_name};")

        try:
            # Step 2: Ingest unprocessed activation events under active write lock
            if self.workspace_hash:
                from memory_utils import legacy_workspace_hash
                target_path = self.workspace_root
                if not target_path:
                    row_path = cur.execute("SELECT workspace_path FROM workspace_registry WHERE workspace_hash = ? LIMIT 1;", (self.workspace_hash,)).fetchone()
                    if row_path and row_path[0]:
                        target_path = row_path[0]
                leg_h = legacy_workspace_hash(target_path) if target_path else self.workspace_hash
                match_hashes = set(self.authorized_hashes) if self.authorized_hashes else set()
                match_hashes.add(self.workspace_hash)
                if target_path:
                    match_hashes.add(target_path)
                if leg_h:
                    match_hashes.add(leg_h)
                query_hashes = [h for h in match_hashes if h and len(str(h)) <= 4096][:900]
                placeholders = ",".join("?" for _ in query_hashes)
                cur.execute(
                    f"""
                    SELECT event_id, session_id, timestamp, user_input, workspace_dir, feedback_score
                    FROM activation_events
                    WHERE is_consolidated = 0 AND workspace_dir IN ({placeholders})
                    ORDER BY event_id ASC
                    LIMIT ?;
                    """,
                    (*query_hashes, batch_size)
                )
            else:
                cur.execute(
                    """
                    SELECT event_id, session_id, timestamp, user_input, workspace_dir, feedback_score
                    FROM activation_events
                    WHERE is_consolidated = 0
                    ORDER BY event_id ASC
                    LIMIT ?;
                    """,
                    (batch_size,)
                )
            events = cur.fetchall()

            # Step 3: Cluster events by normalized folded query
            clusters: Dict[str, List[Dict[str, Any]]] = {}
            processed_ids = []
            dead_letter_ids = []

            for ev in events:
                ev_id, sess_id, ts, user_inp, ws_dir, fb = ev
                if not user_inp or fb < 0.0:
                    processed_ids.append(ev_id)
                    continue

                try:
                    # Determine workspace hash safely with root containment
                    ws_hash = resolve_workspace_hash(ws_dir, approved_root=self.workspace_root, allow_unscoped=(self.workspace_root is None or self.allow_unscoped), authorized_hashes=self.authorized_hashes)
                    # Normalized clustering key combining workspace and redacted folded query (VULN-005)
                    clean_user_inp = redact_secrets(user_inp.strip()) if user_inp else ""
                except Exception as ev_err:
                    redacted_ev_err = persist_diag(ev_err)
                    sys.stderr.write(f"[!] Warning: Quarantining invalid event {ev_id}: {redacted_ev_err}\n")
                    dead_letter_ids.append((ev_id, redacted_ev_err))
                    continue

                norm_query = fold_vietnamese(clean_user_inp)
                cluster_key = f"{ws_hash}::{norm_query}"
                clusters.setdefault(cluster_key, []).append({
                    "id": ev_id,
                    "input": clean_user_inp,
                    "ws_dir": ws_dir,
                    "ws_hash": ws_hash,
                    "feedback": fb
                })
                processed_ids.append(ev_id)

            # Step 4: Trace Frequency Promotion (>= 2 positive hits with feedback_score > 0.0)
            promoted_count = 0
            promoted_ws_hashes = set()
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            for key, cluster_events in clusters.items():
                positive_hits = [e for e in cluster_events if e.get("feedback", 0.0) > 0.0]
                if len(positive_hits) >= 2:
                    rep = positive_hits[0]
                    raw_text = rep["input"]
                    ws_dir = rep["ws_dir"]
                    ws_hash = rep["ws_hash"]
                    cluster_event_ids = [e["id"] for e in cluster_events]

                    # VULN-005: Wrap per-cluster promotion in SAVEPOINT for strict atomicity across episodic & outbox tables
                    sp_prom = f"sp_prom_{uuid.uuid4().hex[:12]}"
                    cur.execute(f"SAVEPOINT {sp_prom};")
                    try:
                        clean_sig = redact_secrets(raw_text) or ""
                        if not clean_sig or not any(c.isalnum() for c in clean_sig):
                            sys.stderr.write(f"[!] Warning: Quarantining empty/non-alphanumeric signature in cluster {key}\n")
                            cur.execute(f"RELEASE SAVEPOINT {sp_prom};")
                            for dl_eid in cluster_event_ids:
                                if dl_eid in processed_ids:
                                    processed_ids.remove(dl_eid)
                                dead_letter_ids.append((dl_eid, "Quarantined: Empty or non-alphanumeric problem signature"))
                            continue
                        tags = extract_bilingual_tags(clean_sig)
                        folded_content = fold_vietnamese(f"{clean_sig} {tags}")
                        clean_sol = f"# Verified Fix for: {clean_sig}"

                        # Use SHA-256 for memory_id while checking legacy MD5 to prevent record duplication (VULN-004)
                        mem_id = f"trace-{hashlib.sha256(f'{ws_hash}:{key}'.encode('utf-8')).hexdigest()[:16]}"
                        legacy_mem_id = f"trace-{hashlib.md5(f'{ws_hash}:{key}'.encode('utf-8')).hexdigest()[:12]}"

                        cur.execute(
                            "SELECT memory_id, activation_count FROM workspace_episodic_memory WHERE (memory_id = ? OR memory_id = ?) AND workspace_hash = ?",
                            (mem_id, legacy_mem_id, ws_hash)
                        )
                        existing = cur.fetchone()
                        if existing:
                            mem_id = existing[0]  # Reuse existing ID (whether legacy or new) to prevent duplicate rows

                        if existing:
                            # Reinforce existing trace (restores confidence to 1.0 and activates)
                            cur.execute(
                                """
                                UPDATE workspace_episodic_memory
                                SET activation_count = activation_count + ?,
                                    confidence_score = 1.0,
                                    last_accessed_at = ?,
                                    status = 'Active'
                                WHERE memory_id = ? AND workspace_hash = ?
                                """,
                                (len(positive_hits), now_str, mem_id, ws_hash)
                            )
                        else:
                            ep_ws_path = self.workspace_root or (ws_dir if ws_dir and not is_valid_hex_hash(ws_dir) else "")
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
                                    mem_id, ws_hash, ep_ws_path,
                                    f"Promoted: {clean_sig[:80]}",
                                    clean_sig,
                                    clean_sol,
                                    tags,
                                    folded_content,
                                    len(positive_hits),
                                    now_str, now_str
                                )
                            )

                        clean_tags_list = [t.strip() for t in tags.split(",") if t.strip()]
                        cur.execute(
                            """
                            INSERT INTO consolidation_outbox (
                                memory_id, workspace_hash, signature, solution, tags, context, status, created_at, generation
                            ) VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, 1)
                            ON CONFLICT(memory_id, workspace_hash) DO UPDATE SET
                                signature = excluded.signature,
                                solution = excluded.solution,
                                tags = excluded.tags,
                                context = excluded.context,
                                status = 'Pending',
                                generation = consolidation_outbox.generation + 1,
                                retry_count = 0,
                                last_error = NULL,
                                owner_token = NULL,
                                claimed_at = NULL;
                            """,
                            (
                                mem_id, ws_hash, clean_sig, clean_sol,
                                json.dumps(clean_tags_list), ws_dir, now_str
                            )
                        )
                        cur.execute(f"RELEASE SAVEPOINT {sp_prom};")
                        promoted_count += 1
                        promoted_ws_hashes.add(ws_hash)
                    except Exception as prom_err:
                        try:
                            cur.execute(f"ROLLBACK TO SAVEPOINT {sp_prom};")
                            cur.execute(f"RELEASE SAVEPOINT {sp_prom};")
                        except Exception:
                            pass
                        err_str = f"Promotion error ({type(prom_err).__name__}): {prom_err}"
                        safe_key = safe_err(key)
                        redacted_prom_err = persist_diag(err_str)
                        is_trans = is_transient_io_error(prom_err) or (
                            isinstance(prom_err, sqlite3.OperationalError) and any(w in str(prom_err).lower() for w in ("locked", "busy"))
                        )
                        if is_trans:
                            sys.stderr.write(f"[!] Warning: Transient contention during cluster promotion {safe_key}: {redacted_prom_err} (re-queued for retry)\n")
                            # VULN-002: Transient contention preserves is_consolidated=0 for natural retry
                            for ev_to_retry in cluster_event_ids:
                                if ev_to_retry in processed_ids:
                                    processed_ids.remove(ev_to_retry)
                        else:
                            sys.stderr.write(f"[!] Warning: Quarantining poison pill cluster {safe_key}: {redacted_prom_err}\n")
                            for dl_eid in cluster_event_ids:
                                if dl_eid in processed_ids:
                                    processed_ids.remove(dl_eid)
                                dead_letter_ids.append((dl_eid, redacted_prom_err))

            # Step 5: Bounded Ebbinghaus Decay & Soft-Archiving (Pure SQLite Padé [0/1] Algebraic Bulk Update)
            # VULN-001: Strict workspace_hash scoping to prevent cross-tenant decay, soft-archive, or hard-purge
            soft_archived_count = 0
            antipatterns_archived_count = 0
            if self.workspace_hash:
                cur.execute(
                    """
                    UPDATE workspace_episodic_memory
                    SET confidence_score = COALESCE(
                        MAX(0.0, MIN(1.0,
                            (1.0 + 0.5 * activation_count) /
                            NULLIF((1.0 + 0.5 * activation_count) + decay_rate * MAX(0.0, (julianday('now') - julianday(last_accessed_at))), 0.0)
                        )),
                        confidence_score
                    )
                    WHERE status = 'Active'
                      AND memory_type != 'invariant'
                      AND decay_rate IS NOT NULL
                      AND decay_rate > 0.0
                      AND last_accessed_at IS NOT NULL
                      AND last_accessed_at < datetime('now', '-1 day')
                      AND workspace_hash = ?;
                    """,
                    (self.workspace_hash,)
                )

                # 2. Two-phase soft-archiving: mark Archived when confidence_score < 0.20 past 7-day grace period
                cur.execute(
                    """
                    UPDATE workspace_episodic_memory
                    SET status = 'Archived'
                    WHERE confidence_score < 0.20
                      AND status = 'Active'
                      AND memory_type != 'invariant'
                      AND last_accessed_at IS NOT NULL
                      AND last_accessed_at < datetime('now', '-7 days')
                      AND workspace_hash = ?;
                    """,
                    (self.workspace_hash,)
                )
                soft_archived_count = cur.rowcount

                # 3. Two-phase hard-purge: physical deletion after 30 days in Archived state
                # CRITICAL: Requires last_accessed_at IS NOT NULL to guarantee legacy records are never lost!
                cur.execute(
                    """
                    DELETE FROM workspace_episodic_memory
                    WHERE status = 'Archived'
                      AND last_accessed_at IS NOT NULL
                      AND last_accessed_at < datetime('now', '-30 days')
                      AND workspace_hash = ?;
                    """,
                    (self.workspace_hash,)
                )

                # 4. Proactive TTL Sweep for episodic_antipatterns (Soft-Archive expired failure patterns)
                try:
                    cur.execute(
                        """
                        UPDATE episodic_antipatterns
                        SET status = 'Archived'
                        WHERE status = 'Active'
                          AND (julianday('now') - julianday(created_at)) >= ttl_days
                          AND workspace_hash = ?;
                        """,
                        (self.workspace_hash,)
                    )
                    antipatterns_archived_count += cur.rowcount
                    cur.execute(
                        """
                        DELETE FROM episodic_antipatterns
                        WHERE status = 'Archived'
                          AND (julianday('now') - julianday(created_at)) >= (ttl_days + 30.0)
                          AND workspace_hash = ?;
                        """,
                        (self.workspace_hash,)
                    )
                except Exception as ap_err:
                    persist_diag(f"consolidator.antipatterns_sweep: {type(ap_err).__name__}: {ap_err}", 256)
            elif effective_unscoped:
                cur.execute(
                    """
                    UPDATE workspace_episodic_memory
                    SET confidence_score = COALESCE(
                        MAX(0.0, MIN(1.0,
                            (1.0 + 0.5 * activation_count) /
                            NULLIF((1.0 + 0.5 * activation_count) + decay_rate * MAX(0.0, (julianday('now') - julianday(last_accessed_at))), 0.0)
                        )),
                        confidence_score
                    )
                    WHERE status = 'Active'
                      AND memory_type != 'invariant'
                      AND decay_rate IS NOT NULL
                      AND decay_rate > 0.0
                      AND last_accessed_at IS NOT NULL
                      AND last_accessed_at < datetime('now', '-1 day');
                    """
                )
                cur.execute(
                    """
                    UPDATE workspace_episodic_memory
                    SET status = 'Archived'
                    WHERE confidence_score < 0.20
                      AND status = 'Active'
                      AND memory_type != 'invariant'
                      AND last_accessed_at IS NOT NULL
                      AND last_accessed_at < datetime('now', '-7 days');
                    """
                )
                soft_archived_count = cur.rowcount
                cur.execute(
                    """
                    DELETE FROM workspace_episodic_memory
                    WHERE status = 'Archived'
                      AND last_accessed_at IS NOT NULL
                      AND last_accessed_at < datetime('now', '-30 days');
                    """
                )

                # 4. Global Proactive TTL Sweep for episodic_antipatterns
                try:
                    cur.execute(
                        """
                        UPDATE episodic_antipatterns
                        SET status = 'Archived'
                        WHERE status = 'Active'
                          AND (julianday('now') - julianday(created_at)) >= ttl_days;
                        """
                    )
                    antipatterns_archived_count += cur.rowcount
                    cur.execute(
                        """
                        DELETE FROM episodic_antipatterns
                        WHERE status = 'Archived'
                          AND (julianday('now') - julianday(created_at)) >= (ttl_days + 30.0);
                        """
                    )
                except Exception as ap_err:
                    persist_diag(f"consolidator.unscoped_antipatterns_sweep: {type(ap_err).__name__}: {ap_err}", 256)
            else:
                sys.stderr.write("[!] Notice: Skipping unscoped maintenance phase in consolidate_batch (pass allow_unscoped=True to run globally)\n")

            # Step 6: Mark processed events as consolidated & quarantine dead-letter rows (VULN-010 safe chunked)
            if processed_ids:
                _chunked_execute(cur, "UPDATE activation_events SET is_consolidated = 1 WHERE event_id IN ({placeholders})", processed_ids)
            if dead_letter_ids:
                for dl_id, dl_err in dead_letter_ids:
                    cur.execute("UPDATE activation_events SET is_consolidated = 2, last_error = ? WHERE event_id = ?", (dl_err, dl_id))

            if own_tx:
                self.conn.commit()
            else:
                self.conn.execute(f"RELEASE SAVEPOINT {sp_name};")
        except Exception as dbe:
            if own_tx:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            else:
                try:
                    self.conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name};")
                    self.conn.execute(f"RELEASE SAVEPOINT {sp_name};")
                except Exception:
                    pass
            sys.stderr.write(f"[!] Warning: Step 5 consolidation transaction failed: {type(dbe).__name__}: {dbe}\n")
            raise

        # Step 6b: Durable outbox flush decoupled from consolidation commit scoped by workspace_hash (VULN-004, VULN-005, VULN-006)
        outbox_err = None
        deferred_flushes = []
        if not getattr(self.conn, "in_transaction", False):
            flush_targets = set(promoted_ws_hashes)
            if self.workspace_hash:
                flush_targets.add(self.workspace_hash)
            try:
                if flush_targets:
                    for target_h in flush_targets:
                        flush_outbox(self.conn, workspace_hash=target_h)
                elif effective_unscoped:
                    flush_outbox(self.conn, workspace_hash=None)
            except Exception as foe:
                outbox_err = foe
                sys.stderr.write(f"[!] Warning: flush_outbox after consolidate_batch failed: {safe_err(foe)}\n")
        else:
            flush_targets = set(promoted_ws_hashes)
            if self.workspace_hash:
                flush_targets.add(self.workspace_hash)
            deferred_flushes = list(flush_targets)
            sys.stderr.write(
                f"[!] Notice: consolidate_batch called while outer transaction is active; "
                f"deferring outbox flush for {len(deferred_flushes)} tenant(s) until caller commits.\n"
            )

        # Lazy Vector Backfill (VULN-001): Strict workspace_hash scoping to prevent cross-tenant exfiltration
        try:
            from embedding_service import get_embedding, MODEL_NAME
            from memory_engine import serialize_float32_blob, compute_vector_norm

            if self.workspace_hash:
                cur.execute(
                    """
                    SELECT e.memory_id, e.workspace_hash, e.title, e.problem_signature, e.solution_payload
                    FROM workspace_episodic_memory e
                    LEFT JOIN dense_embeddings d ON e.memory_id = d.memory_id AND e.workspace_hash = d.workspace_hash
                    WHERE e.status = 'Active' AND d.memory_id IS NULL AND e.workspace_hash = ?
                    LIMIT 50;
                    """,
                    (self.workspace_hash,)
                )
                rows_to_backfill = cur.fetchall()
            elif effective_unscoped:
                cur.execute(
                    """
                    SELECT e.memory_id, e.workspace_hash, e.title, e.problem_signature, e.solution_payload
                    FROM workspace_episodic_memory e
                    LEFT JOIN dense_embeddings d ON e.memory_id = d.memory_id AND e.workspace_hash = d.workspace_hash
                    WHERE e.status = 'Active' AND d.memory_id IS NULL
                    LIMIT 50;
                    """
                )
                rows_to_backfill = cur.fetchall()
            else:
                rows_to_backfill = []
            if rows_to_backfill:
                # VULN-003: Compute all embeddings OUTSIDE of SQLite write transaction to prevent lock contention
                computed_embeddings = []
                for row in rows_to_backfill:
                    mem_id, ws_hash, title, sig, sol = row
                    embed_text = f"{title} {sig or ''} {sol}"[:1000]
                    try:
                        vec = get_embedding(embed_text, is_query=False)
                        if vec:
                            norm = compute_vector_norm(vec)
                            blob = serialize_float32_blob(vec)
                            computed_embeddings.append((mem_id, ws_hash, MODEL_NAME, len(vec), blob, norm))
                    except Exception as emb_e:
                        sys.stderr.write(f"[!] Warning: Vector backfill embedding call failed for {mem_id}: {safe_err(emb_e)}\n")

                if computed_embeddings:
                    bf_own = not getattr(self.conn, "in_transaction", False)
                    sp_bf = f"sp_bf_{uuid.uuid4().hex[:12]}"
                    if bf_own:
                        self.conn.execute("BEGIN IMMEDIATE;")
                    else:
                        self.conn.execute(f"SAVEPOINT {sp_bf};")
                    try:
                        for item in computed_embeddings:
                            cur.execute(
                                """
                                INSERT OR REPLACE INTO dense_embeddings (memory_id, workspace_hash, model_name, dimensions, vector_blob, norm, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                                """,
                                item
                            )
                        if bf_own:
                            self.conn.commit()
                        else:
                            self.conn.execute(f"RELEASE SAVEPOINT {sp_bf};")
                    except Exception as row_e:
                        if bf_own:
                            try:
                                self.conn.rollback()
                            except Exception:
                                pass
                        else:
                            try:
                                self.conn.execute(f"ROLLBACK TO SAVEPOINT {sp_bf};")
                                self.conn.execute(f"RELEASE SAVEPOINT {sp_bf};")
                            except Exception:
                                pass
                        raise row_e
        except Exception as bfe:
            sys.stderr.write(f"[!] Warning: Vector backfill failed: {type(bfe).__name__}: {safe_err(bfe)}\n")

        # Incremental WAL vacuuming & Passive Checkpoint (Argon Chốt chặn 2)
        if not getattr(self.conn, "in_transaction", False):
            try:
                self.conn.execute("PRAGMA incremental_vacuum(100);")
                self.conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
            except Exception as wce:
                sys.stderr.write(f"[!] Warning: WAL maintenance failed: {type(wce).__name__}: {wce}\n")

        batch_res = {
            "events_processed": len(processed_ids),
            "promoted_traces": promoted_count,
            "soft_archived": soft_archived_count,
            "antipatterns_archived": antipatterns_archived_count
        }
        if deferred_flushes:
            batch_res["pending_flushes"] = deferred_flushes
        if outbox_err is not None:
            batch_res["outbox_error"] = safe_err(outbox_err)
        return batch_res


def main():
    parser = argparse.ArgumentParser(description="Omni-Memory v4.1 Background Consolidator")
    parser.add_argument("--workspace", default=None, help="Target workspace root path")
    parser.add_argument("--allow-unscoped", action="store_true", help="Allow unscoped global consolidation across all workspaces")
    parser.add_argument("--batch-run", action="store_true", help="Run batch consolidation cycle")
    parser.add_argument("--dry-run", action="store_true", help="Simulate consolidation without persisting")
    parser.add_argument("--daemon", action="store_true", help="Run as standing daemon with idle auto-exit")
    parser.add_argument("--idle-timeout", type=int, default=3600, help="Auto-exit after idle seconds")
    args = parser.parse_args()

    target_ws = args.workspace.strip() if (args.workspace and isinstance(args.workspace, str) and args.workspace.strip()) else None
    if not target_ws and not args.allow_unscoped:
        sys.stderr.write("[!] LỖI VẬN HÀNH: Consolidator requires an explicit --workspace path or --allow-unscoped flag\n")
        sys.exit(1)

    # Lifecycle & Mutual Exclusion Guard (Anti-Zombie & Auto-Healing Lock)
    from lifecycle_guard import LifecycleGuard
    guard = LifecycleGuard("omni_consolidator")
    if not guard.acquire_lock(stale_timeout_sec=60.0):
        print(json.dumps({"status": "skipped", "reason": "Another consolidator is currently running"}))
        return

    # Mode A: Monitor parent process (IDE/Agent). Immediate termination on parent exit.
    guard.start_parent_watcher()

    db_path = os.path.join(_SCRIPT_DIR, "..", "omni_memory.db")
    conn = init_database(db_path)
    guard.register_cleanup(lambda: conn.close())

    try:
        engine = ConsolidatorEngine(conn, workspace_root=target_ws, allow_unscoped=args.allow_unscoped)
        if args.daemon:
            last_activity = time.time()
            print("🚀 Consolidator daemon started. Monitoring L1 events...")
            while True:
                res = engine.consolidate_batch(batch_size=100, dry_run=args.dry_run)
                if res.get("status") == "unconfigured_unscoped_error":
                    sys.stderr.write("[!] LỖI VẬN HÀNH: Consolidator daemon aborted due to unconfigured workspace\n")
                    sys.exit(1)
                if res.get("events_processed", 0) > 0 or res.get("promoted_traces", 0) > 0:
                    last_activity = time.time()
                elif time.time() - last_activity > args.idle_timeout:
                    print(f"✔ Consolidator idle for {args.idle_timeout}s without new events. Exiting cleanly.")
                    break
                time.sleep(30)
        else:
            result = engine.consolidate_batch(batch_size=100, dry_run=args.dry_run)
            print(json.dumps(result, indent=2))
            if result.get("status") == "unconfigured_unscoped_error":
                sys.stderr.write("[!] LỖI VẬN HÀNH: Consolidator batch run failed due to unconfigured workspace\n")
                sys.exit(1)
    finally:
        guard.stop()


if __name__ == "__main__":
    main()
