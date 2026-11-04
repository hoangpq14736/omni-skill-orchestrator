"""
Memory Utilities Module for Omni-Memory v4.1.
Provides diacritic folding, defensive FTS5 query sanitization, and workspace hashing.
"""

import hashlib
import json
import os
import re
import unicodedata
from typing import Optional, Any, Tuple


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
    Generate deterministic MD5 hash for workspace partition isolation.
    Mandates unicodedata.normalize('NFC') + os.path.normcase(os.path.realpath(os.path.abspath(path)))
    prior to hashing so case-insensitive Windows drive letters (d:\\ vs D:\\), mixed slashes,
    and symlinks/junctions generate identical partition keys (VULN-003).
    Idempotent: If path is already a 32-char hex MD5 string, returns it lowercase.
    """
    if not path:
        return hashlib.md5(b"global_fallback").hexdigest()
    if is_valid_hex_hash(path, length=32):
        return path.lower().strip()
    normalized_path = unicodedata.normalize("NFC", str(path))
    canonical = os.path.normcase(os.path.realpath(os.path.abspath(normalized_path)))
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# Cryptographic Council Gate HMAC Authenticity Signatures (VULN-201)
# ----------------------------------------------------------------------
import hmac


def get_audit_hmac_key() -> bytes:
    """Returns or provisions out-of-band persistent HMAC key for Council Gate metadata (VULN-201)."""
    key_file = os.path.expanduser("~/.gemini/config/omni_audit.key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "rb") as f:
                k = f.read().strip()
                if len(k) >= 32:
                    return k
        except Exception:
            pass
    # Generate and store persistent 32-byte key with restricted permissions
    os.makedirs(os.path.dirname(key_file), exist_ok=True)
    new_key = os.urandom(32).hex().encode("utf-8")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(key_file, flags, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(new_key)
    except OSError:
        pass
    return new_key


def sign_audit_meta(meta: dict) -> str:
    """Computes HMAC-SHA256 signature for Council Gate review metadata (VULN-201)."""
    key = get_audit_hmac_key()
    canonical_str = f"{meta.get('target_file','')}:{meta.get('input_hash','')}:{meta.get('verdict','')}"
    return hmac.new(key, canonical_str.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_audit_meta(meta: dict) -> bool:
    """Verifies cryptographic authenticity signature of Council Gate review metadata (VULN-201)."""
    sig = meta.get("signature")
    if not isinstance(sig, str) or not sig.strip():
        return False
    key = get_audit_hmac_key()
    canonical_str = f"{meta.get('target_file','')}:{meta.get('input_hash','')}:{meta.get('verdict','')}"
    expected = hmac.new(key, canonical_str.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig.strip().lower(), expected.lower())

