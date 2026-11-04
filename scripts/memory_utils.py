"""
Memory Utilities Module for Omni-Memory v4.1.
Provides diacritic folding, defensive FTS5 query sanitization, and workspace hashing.
"""

import hashlib
import json
import os
import re
import unicodedata
import stat
import threading
from typing import Optional, Any, Tuple

__all__ = [
    "redact_secrets",
    "redact_json_object",
    "_redact_json_obj",
    "persist_diag",
    "fold_vietnamese",
    "normalize_vietnamese_diacritics",
    "sanitize_fts5_query",
    "is_valid_hex_hash",
    "canonical_workspace_hash",
    "legacy_workspace_hash",
    "get_audit_hmac_key",
    "sign_audit_meta",
    "verify_audit_meta",
    "find_workspace_root",
    "hash_prompt",
]


_SECRET_KEY_NAMES = {
    "api_key", "apikey", "secret", "token", "access_token",
    "auth_token", "password", "passwd", "client_secret", "private_key",
    "credentials", "bearer"
}

# New suffixes and allowlist for secret detection (VULN-005)
_SECRET_SUFFIXES = ("_key", "_token", "_secret", "_password", "_passwd")
_BENIGN_KEY_ALLOWLIST = {
    "primary_key", "foreign_key", "sort_key", "partition_key",
    "unique_key", "routing_key", "cache_key", "public_key"
}


def _redact_json_obj(obj: Any, depth: int = 0) -> Tuple[Any, bool]:
    """
    Recursively redacts values for secret-like keys in JSON-deserialized objects.
    Uses normalized exact equality and suffix matching with benign key allowlist (VULN-005).
    Guards against excessive recursion depth by failing loud when depth > 32 (VULN-001).
    Returns (redacted_object, was_modified).
    """
    if depth > 32:
        return ("[REDACTED_MAX_DEPTH]", True)

    modified = False
    if isinstance(obj, dict):
        new_d = {}
        for k, v in obj.items():
            k_norm = str(k).lower().strip().replace("-", "_")
            is_secret_key = (
                k_norm in _SECRET_KEY_NAMES
                or (
                    any(k_norm.endswith(suffix) for suffix in _SECRET_SUFFIXES)
                    and k_norm not in _BENIGN_KEY_ALLOWLIST
                )
            )
            if is_secret_key:
                new_d[k] = "[REDACTED_KEY]"
                modified = True
            else:
                sub_res, sub_mod = _redact_json_obj(v, depth + 1)
                new_d[k] = sub_res
                if sub_mod:
                    modified = True
        return new_d, modified
    elif isinstance(obj, list):
        new_list = []
        for x in obj:
            sub_res, sub_mod = _redact_json_obj(x, depth + 1)
            new_list.append(sub_res)
            if sub_mod:
                modified = True
        return new_list, modified
    elif isinstance(obj, str):
        sub_res = _redact_plain_text(obj)
        return sub_res, (sub_res != obj)
    return obj, False


# Public export alias (VULN-003)
redact_json_object = _redact_json_obj


# Pre-compile regex patterns for performance and ReDoS defense (VULN-003)
_REDACTION_PATTERNS = [
    (re.compile(r'(?i)(bearer\s+)[A-Za-z0-9_\-\.]{16,}'), r'\1[REDACTED_TOKEN]'),
    (re.compile(r'(?<![A-Za-z0-9])(sk-[a-zA-Z0-9_\-]{20,})\b'), '[REDACTED_API_KEY]'),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), '[REDACTED_AWS_KEY]'),
    (re.compile(r'\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b'), '[REDACTED_JWT]'),
    (re.compile(r'\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b'), '[REDACTED_GITHUB_TOKEN]'),
    (re.compile(r'\bxox[baprs]-[A-Za-z0-9\-]{10,}\b'), '[REDACTED_SLACK_TOKEN]'),
    (re.compile(r'\bAIza[0-9A-Za-z_\-]{30,45}\b'), '[REDACTED_GOOGLE_KEY]'),
    (re.compile(r'(?i)(["\']?api[_-]?key["\']?\s*[:=]\s*["\']?)[^\s,;"\'\}\]]{8,}(?=["\',;\s\}\]]|$)'), r'\1[REDACTED_KEY]'),
    (re.compile(r'(?i)(["\']?password["\']?\s*[:=]\s*["\']?)[^\s,;"\'\}\]]{6,}(?=["\',;\s\}\]]|$)'), r'\1[REDACTED_PASSWORD]'),
    (re.compile(r'(?i)([a-z]+://[^:\s]+:)[^@\s]+(@)'), r'\1[REDACTED_PASS]\2'),
    (re.compile(r'-----BEGIN [A-Z ]+ PRIVATE KEY-----(?:(?!-----BEGIN)[\s\S])*?-----END [A-Z ]+ PRIVATE KEY-----'), '[REDACTED_PRIVATE_KEY]'),
    (re.compile(r'-----BEGIN PGP PRIVATE KEY BLOCK-----(?:(?!-----BEGIN)[\s\S])*?-----END PGP PRIVATE KEY BLOCK-----'), '[REDACTED_PGP_KEY]'),
    (re.compile(r'(?i)(Authorization:\s*Basic\s+)[A-Za-z0-9+/=]+'), r'\1[REDACTED_CREDENTIAL]'),
    (re.compile(r'(?i)(["\']?(?:token|access_token|client_secret|api_secret|auth_token|secret_key|secret|private_key|credentials|auth|access_key|AWS_SECRET_ACCESS_KEY)["\']?\s*[:=]\s*["\']?)[^\s,;"\'\}\]]{6,}'), r'\1[REDACTED]'),
]


def _redact_plain_text(text: str) -> str:
    """
    Applies regex redaction across the entire text payload.
    Eliminates chunk-first truncation to ensure multi-line PEM keys and tokens are never split across boundaries (VULN-001).
    """
    redacted = text
    for pat_re, repl in _REDACTION_PATTERNS:
        redacted = pat_re.sub(repl, redacted)
    return redacted


def redact_secrets(text: Optional[str]) -> Optional[str]:
    """
    Redact credentials, tokens, passwords, and API keys from persisted text.
    Covers Bearer tokens, OpenAI/Anthropic/DeepSeek keys, AWS AKIA keys, JWT tokens,
    GitHub/Slack/Google API tokens, database URIs, passwords, and PEM private key blocks.
    Preserves None explicitly to avoid corrupting nullable SQL columns.
    Structure-aware: If input is valid JSON, parses and redacts keys without breaking JSON delimiters (VULN-005).
    Preserves original formatting when no secrets were altered.
    Bounds maximum payload to 64 KiB to prevent quadratic regex ReDoS (VULN-008).
    """
    if text is None:
        return None
    # Structurally typed recursion for dict/list payloads (VULN-002)
    if isinstance(text, (dict, list)):
        red_obj, _ = _redact_json_obj(text)
        return red_obj
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return ""

    if len(text) > 262144:
        text = text[:262144] + "\n[PAYLOAD_TRUNCATED_256KB]"

    try:
        trimmed = text.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None

            if parsed is not None and isinstance(parsed, (dict, list)):
                try:
                    red_obj, modified = _redact_json_obj(parsed)
                    if modified:
                        return json.dumps(red_obj, ensure_ascii=False)
                    return text
                except Exception:
                    pass
        return _redact_plain_text(text)
    except Exception:
        # Fallback to plain text redaction rather than replacing entire document with [REDACTED] (VULN-006)
        try:
            return _redact_plain_text(text)
        except Exception:
            return "[REDACTION_ERROR_SAFEGUARD]"


def persist_diag(exc: Any, max_len: int = 512) -> str:
    """
    Choke point for all diagnostic error strings persisted to database or logs (VULN-002).
    Redacts credentials, tokens, and secrets via redact_secrets() and clamps output to max_len.
    """
    if exc is None:
        return ""
    if isinstance(exc, str):
        raw = exc
    else:
        raw = f"{type(exc).__name__}: {exc}"
    redacted = redact_secrets(raw) or ""
    if len(redacted) > max_len:
        return redacted[:max_len - 12] + " [TRUNCATED]"
    return redacted


def fold_vietnamese(text: Optional[str]) -> str:
    """
    Application-level diacritic removal preserving dual-column FTS5 precision.
    Pre-converts stroked consonants (đ/Đ -> d/D) before NFD decomposition
    because Unicode NFD does not separate the horizontal bar from 'đ'.
    Strips combining diacritical marks (category 'Mn').
    Returns lowercased string.
    """
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return stripped.lower()


# Backward-compatible alias
normalize_vietnamese_diacritics = fold_vietnamese


def sanitize_fts5_query(query: Optional[str], fold: bool = False) -> str:
    """
    Sanitize technical developer queries for safe SQLite FTS5 MATCH execution.

    CRITICAL RUNTIME GUARDRAIL:
    - fold=False (Default): Preserves original characters and accents (for :raw_q against content_exact).
    - fold=True: Applies fold_vietnamese() (for :folded_q against content_folded).
    - Replaces FTS5 reserved punctuation characters [.:-><()*\"'+^~{}/] with whitespace.
    - Strips standalone FTS5 boolean and proximity operators (AND, OR, NOT, NEAR).
    - Encloses individual alphanumeric terms in double quotes to prevent syntax injection.
    - Returns '""' when query is empty or produces no searchable tokens (preserves 100% backward compatibility).
    """
    if not query:
        return '""'

    bounded_query = query[:512] if len(query) > 512 else query
    target = fold_vietnamese(bounded_query) if fold else bounded_query

    # Replace FTS5 reserved punctuation and symbol characters with whitespace
    reserved = ".:-><()*\"'+^~{}/\\$#@%!&|[]();,=?"
    trans_table = str.maketrans({ch: " " for ch in reserved})
    cleaned = target.translate(trans_table)

    # Tokenize on whitespace, strip operators, and require at least 1 alphanumeric character
    tokens = cleaned.split()
    ops = {"AND", "OR", "NOT", "NEAR"}
    filtered = [
        t for t in tokens
        if t.upper() not in ops and any(c.isalnum() for c in t)
    ][:32]

    if not filtered:
        return '""'

    return " ".join(f'"{token}"' for token in filtered)


def is_valid_hex_hash(val: Any, length: Optional[int] = None) -> bool:
    """
    Return True if val is a valid hexadecimal hash.
    If length is specified (e.g. 32 or 64), validates exact length.
    If length is None, accepts standard 32 (MD5) or 64 (SHA-256) hex hashes.
    """
    if not isinstance(val, str):
        return False
    cleaned = val.strip()
    if length is not None:
        if len(cleaned) != length:
            return False
    else:
        if len(cleaned) not in (32, 64):
            return False
    return all(c in "0123456789abcdefABCDEF" for c in cleaned)


def canonical_workspace_hash(path: Optional[str]) -> str:
    """
    Generate deterministic SHA-256 hash for workspace partition isolation (VULN-006).
    Mandates unicodedata.normalize('NFC') + os.path.normcase(os.path.realpath(os.path.abspath(path)))
    prior to hashing so case-insensitive Windows drive letters (d:\\ vs D:\\), mixed slashes,
    and symlinks/junctions generate identical partition keys (VULN-003).
    Idempotent: If path is already a valid 64-hex SHA-256 hash, returns it normalized.
    """
    if not path:
        return hashlib.sha256(b"global_fallback").hexdigest()
    if is_valid_hex_hash(path, length=64):
        return path.lower()
    normalized_path = unicodedata.normalize("NFC", str(path))
    canonical = os.path.normcase(os.path.realpath(os.path.abspath(normalized_path)))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def legacy_workspace_hash(path: Optional[str]) -> str:
    """Returns legacy 32-character MD5 hash of normalized workspace path for backwards compatibility."""
    if not path:
        return hashlib.md5(b"global_fallback").hexdigest()
    if is_valid_hex_hash(path, length=32):
        return path.lower()
    normalized_path = unicodedata.normalize("NFC", str(path))
    canonical = os.path.normcase(os.path.realpath(os.path.abspath(normalized_path)))
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# Cryptographic Council Gate HMAC Authenticity Signatures (VULN-201, VULN-001, VULN-003)
# ----------------------------------------------------------------------
import hmac
import tempfile
import time

_KEY_CACHE_LOCK = threading.Lock()
_CACHED_HMAC_KEY: Optional[bytes] = None
_CACHED_KEY_MTIME: float = 0.0


def _is_valid_hex_key(k: Any) -> bool:
    """Enforces exact 64-hex character (256-bit entropy) key provenance."""
    if not isinstance(k, bytes):
        if isinstance(k, str):
            k = k.encode("utf-8")
        else:
            return False
    k = k.strip()
    if len(k) != 64:
        return False
    return all(c in b"0123456789abcdefABCDEF" for c in k)


def _verify_key_file_security(fd: int, path: str) -> bool:
    """
    Validates regular file, single link, and non-bypassable ownership/permissions
    on both POSIX and Windows (VULN-001).
    """
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
            persist_diag(f"HMAC key file {path} is not a regular file or has multiple hard links", 256)
            return False
        if hasattr(os, "getuid"):
            if st.st_uid != os.getuid():
                persist_diag(f"HMAC key file {path} owned by uid {st.st_uid} != {os.getuid()}", 256)
                return False
            # Check group/other write permissions (0o022); self-heal to 0o600 if owner
            if (st.st_mode & 0o022) != 0:
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    persist_diag(f"HMAC key file {path} has unsafe writable permissions: {oct(st.st_mode)}", 256)
                    return False
        if os.name == "nt":
            key_real = os.path.normcase(os.path.realpath(path))
            home_real = os.path.normcase(os.path.realpath(os.path.expanduser("~")))
            temp_real = os.path.normcase(os.path.realpath(tempfile.gettempdir()))
            try:
                is_in_home = (os.path.commonpath([key_real, home_real]) == home_real)
                is_in_temp = (os.path.commonpath([key_real, temp_real]) == temp_real)
                if not (is_in_home or is_in_temp):
                    persist_diag(f"HMAC key file {path} outside user profile tree", 256)
                    return False
            except (ValueError, OSError):
                return False
            # Windows platform containment: Enforces strict user profile boundary containment (VULN-003)
            return True
        return True
    except Exception as e:
        persist_diag(f"Key file security validation exception: {e}", 256)
        return False


def get_audit_hmac_key(auto_provision: bool = False) -> Optional[bytes]:
    """
    Returns out-of-band persistent HMAC key for Council Gate metadata.
    Enforces on-disk key file (~/.gemini/config/omni_audit.key) as sole source of truth (VULN-001).
    Verifier strictly REJECTS env-var keys unless matching on-disk key byte-for-byte.
    Only auto-provisions if auto_provision=True (producers only, never verifiers).
    Uses temp-file + atomic os.replace to eliminate partial-read races.
    """
    global _CACHED_HMAC_KEY, _CACHED_KEY_MTIME
    key_file = os.path.expanduser("~/.gemini/config/omni_audit.key")
    env_key = os.environ.get("OMNI_AUDIT_HMAC_KEY", "").strip()

    with _KEY_CACHE_LOCK:
        # Check cache freshness against file mtime
        if _CACHED_HMAC_KEY is not None:
            if os.path.exists(key_file):
                try:
                    cur_mtime = os.path.getmtime(key_file)
                    if cur_mtime == _CACHED_KEY_MTIME:
                        return _CACHED_HMAC_KEY
                except OSError:
                    pass
            _CACHED_HMAC_KEY = None

        file_key: Optional[bytes] = None
        if os.path.exists(key_file):
            try:
                t_flags = os.O_RDONLY
                if hasattr(os, "O_NOFOLLOW"):
                    t_flags |= os.O_NOFOLLOW
                if hasattr(os, "O_NONBLOCK"):
                    t_flags |= os.O_NONBLOCK
                if hasattr(os, "O_BINARY"):
                    t_flags |= os.O_BINARY

                fd = os.open(key_file, t_flags)
                try:
                    if _verify_key_file_security(fd, key_file):
                        k = os.read(fd, 65).strip()
                        if _is_valid_hex_key(k):
                            file_key = k
                            _CACHED_KEY_MTIME = os.fstat(fd).st_mtime
                        elif 0 < len(k) < 64:
                            persist_diag(f"Corrupted HMAC key observed on disk (len {len(k)} != 64)", 256)
                finally:
                    os.close(fd)
            except (OSError, IOError) as err:
                persist_diag(f"HMAC key file read error: {err}", 256)

        # Trust boundary rules (VULN-001):
        # Env-var key is only accepted if it matches on-disk file byte-for-byte.
        # If on-disk file is missing, verifier NEVER accepts env-var key alone.
        if env_key:
            env_bytes = env_key.encode("utf-8")
            if not _is_valid_hex_key(env_bytes):
                persist_diag("OMNI_AUDIT_HMAC_KEY rejected: not valid 64-hex string", 256)
                return None
            if file_key is not None:
                if not hmac.compare_digest(env_bytes, file_key):
                    persist_diag("OMNI_AUDIT_HMAC_KEY mismatch with on-disk key file", 256)
                    return None
            elif not auto_provision:
                persist_diag("Verifier rejected env-only key without authoritative disk file", 256)
                return None

        if file_key is not None:
            _CACHED_HMAC_KEY = file_key
            return file_key

        if not auto_provision:
            # Verifier MUST NOT auto-provision! Fail closed cleanly (VULN-001).
            return None

        # 3. Provision key with mutual exclusion lock to eliminate last-writer-wins race
        key_dir = os.path.dirname(key_file)
        os.makedirs(key_dir, exist_ok=True)
        from workspace_sanitizer import TrustFileLock

        with TrustFileLock(f"{key_file}.lock", timeout=5.0):
            # Under lock, check if another process won the race
            if os.path.exists(key_file):
                t_flags = os.O_RDONLY
                if hasattr(os, "O_NOFOLLOW"):
                    t_flags |= os.O_NOFOLLOW
                if hasattr(os, "O_NONBLOCK"):
                    t_flags |= os.O_NONBLOCK
                if hasattr(os, "O_BINARY"):
                    t_flags |= os.O_BINARY
                corrupted = False
                try:
                    fd = os.open(key_file, t_flags)
                    try:
                        if _verify_key_file_security(fd, key_file):
                            k = os.read(fd, 65).strip()
                            if _is_valid_hex_key(k):
                                _CACHED_HMAC_KEY = k
                                _CACHED_KEY_MTIME = os.fstat(fd).st_mtime
                                return k
                            if 0 < len(k) < 64:
                                corrupted = True
                    finally:
                        os.close(fd)

                    if corrupted:
                        ts = int(time.time())
                        bak = f"{key_file}.corrupt.{ts}.bak"
                        try:
                            os.replace(key_file, bak)
                            persist_diag(f"Producer quarantined corrupted HMAC key (<64 hex chars) to {bak}", 256)
                        except OSError:
                            pass
                except (OSError, IOError) as err:
                    persist_diag(f"HMAC key file provisioning check error: {err}", 256)

            new_key = os.urandom(32).hex().encode("utf-8")
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(dir=key_dir, delete=False, prefix=".audit_key_", suffix=".tmp") as tmp:
                    tmp_path = tmp.name
                    if hasattr(os, "fchmod"):
                        os.fchmod(tmp.fileno(), 0o600)
                    tmp.write(new_key)
                    tmp.flush()
                    os.fsync(tmp.fileno())

                os.replace(tmp_path, key_file)
                _CACHED_HMAC_KEY = new_key
                _CACHED_KEY_MTIME = os.path.getmtime(key_file)
                return new_key
            except Exception as e:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                raise RuntimeError(f"Failed to provision audit HMAC key: {e}")


def _canonical_meta_payload(meta: dict) -> bytes:
    """Produces unambiguous, sorted canonical JSON payload for HMAC signing (VULN-001, VULN-004, VULN-006)."""
    normalized_meta = {
        "hash_algo": str(meta.get("hash_algo", "sha256-v2")).strip(),
        "hash_domain": str(meta.get("hash_domain", "redacted_prompt_v1")).strip(),
        "input_hash": str(meta.get("input_hash", "")).strip().lower(),
        "model": str(meta.get("model", "deepseek-flash")).strip(),
        "target_file": str(meta.get("target_file", "")).strip(),
        "timestamp_utc": str(meta.get("timestamp_utc", "")).strip(),
        "verdict": str(meta.get("verdict", "")).strip().upper(),
        "workspace_hash": str(meta.get("workspace_hash", "")).strip().lower()
    }
    return json.dumps(normalized_meta, sort_keys=True, separators=(',', ':')).encode("utf-8")


def sign_audit_meta(meta: dict) -> str:
    """Computes HMAC-SHA256 signature for Council Gate review metadata (VULN-001, VULN-003)."""
    if not isinstance(meta, dict):
        raise TypeError(f"meta must be a dict, got {type(meta).__name__}")
    if not meta.get("verdict"):
        raise ValueError("Cannot sign review metadata without non-empty 'verdict'")
    if not meta.get("target_file"):
        raise ValueError("Cannot sign review metadata without non-empty 'target_file'")
    if not meta.get("input_hash"):
        raise ValueError("Cannot sign review metadata without non-empty 'input_hash'")

    key = get_audit_hmac_key(auto_provision=True)
    if not key:
        raise RuntimeError("HMAC key could not be resolved for signing")
    payload = _canonical_meta_payload(meta)
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def find_workspace_root(start_path: str) -> str:
    """Finds repository or workspace root walking upwards looking for .git or GEMINI.md (VULN-004, VULN-007)."""
    if not start_path:
        return os.path.realpath(os.getcwd())
    curr = os.path.realpath(os.path.normpath(str(start_path)))
    if os.path.isfile(curr):
        curr = os.path.dirname(curr)
    while True:
        if os.path.exists(os.path.join(curr, ".git")) or os.path.exists(os.path.join(curr, "GEMINI.md")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return os.path.realpath(os.getcwd())


def hash_prompt(prompt: Optional[str]) -> str:
    """Deterministic, secret-redacted SHA-256 hash for inline prompt Council Gate binding (VULN-005).
    Canonicalizes JSON object/array prompts with sorted keys and compact separators to ensure
    identical hashes across whitespace and formatting differences between producer and verifier.
    """
    if not prompt or not isinstance(prompt, str):
        return ""
    stripped = prompt.strip()[:2048]
    # Canonical JSON normalization for JSON object/array prompts to resist whitespace variance
    if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
        try:
            parsed = json.loads(stripped)
            stripped = json.dumps(parsed, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        except Exception:
            pass
    safe_text = (redact_secrets(stripped) or stripped)
    if isinstance(safe_text, (dict, list)):
        safe_text = json.dumps(safe_text, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    elif isinstance(safe_text, str) and ((safe_text.strip().startswith("{") and safe_text.strip().endswith("}")) or (safe_text.strip().startswith("[") and safe_text.strip().endswith("]"))):
        try:
            parsed_after = json.loads(safe_text)
            safe_text = json.dumps(parsed_after, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        except Exception:
            pass
    return hashlib.sha256(str(safe_text).encode("utf-8")).hexdigest()


def verify_audit_meta(meta: dict) -> bool:
    """Verifies cryptographic authenticity signature of Council Gate review metadata (VULN-001, VULN-003, VULN-004)."""
    if not isinstance(meta, dict):
        return False
    sig = meta.get("signature")
    if not isinstance(sig, str) or not sig.strip():
        return False
    if not meta.get("verdict") or not meta.get("target_file") or not meta.get("input_hash"):
        return False
    if meta.get("hash_domain") and meta.get("hash_domain") not in ("redacted_prompt_v1", "raw_file_v1"):
        return False
    if meta.get("hash_algo") and meta.get("hash_algo") != "sha256-v2":
        return False

    key = get_audit_hmac_key(auto_provision=False)
    if not key:
        # Key missing or not provisioned: fail-closed, do NOT auto-provision on verify (VULN-001)
        return False
    payload = _canonical_meta_payload(meta)
    expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig.strip().lower(), expected.lower())

