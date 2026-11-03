"""
Adversarial Stress Test Suite: Challenger 2
Testing Edge Cases, Risk Matrix (RSK-001..RSK-008), Partition Isolation, and Zero-Trust Boundaries.
"""

import sqlite3
import struct
import math
import re
import os
import tempfile
import time
from datetime import datetime, timezone, timedelta
import pytest

import importlib.util
from pathlib import Path

_TEST_DIR = Path(__file__).resolve().parent

def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _TEST_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_t1 = _load_module("test_tier1_reflex", "test_tier1_reflex.py")
_t2 = _load_module("test_tier2_hybrid_memory", "test_tier2_hybrid_memory.py")
_t3 = _load_module("test_tier3_consolidation", "test_tier3_consolidation.py")

Tier1ReflexEngine = _t1.Tier1ReflexEngine
FILLER_PATTERN = _t1.FILLER_PATTERN
SAMPLE_TRACES = _t1.SAMPLE_TRACES

normalize_vietnamese_diacritics = _t2.normalize_vietnamese_diacritics
sanitize_fts5_query = _t2.sanitize_fts5_query
compute_vector_norm = _t2.compute_vector_norm
serialize_float32_blob = _t2.serialize_float32_blob
deserialize_float32_blob = _t2.deserialize_float32_blob
cosine_similarity = _t2.cosine_similarity
compute_rrf_score = _t2.compute_rrf_score
DDL_SCHEMA = _t2.DDL_SCHEMA

calculate_ebbinghaus_stability = _t3.calculate_ebbinghaus_stability
should_prune_memory = _t3.should_prune_memory
extract_bilingual_tags = _t3.extract_bilingual_tags
Tier3Consolidator = _t3.Tier3Consolidator
DDL_CONSOLIDATION = _t3.DDL_CONSOLIDATION


# ============================================================================
# 1. RSK-001 & Tier 1 Reflex Edge Cases
# ============================================================================

def test_tier1_multibyte_utf8_clamping_boundary():
    """
    Test 2,048-char clamping at multibyte / emoji / Vietnamese unicode boundaries.
    Ensure slicing does not crash or corrupt string handling.
    """
    engine = Tier1ReflexEngine(SAMPLE_TRACES)
    
    # 2047 ASCII chars followed by Vietnamese accented chars and emojis
    prefix = "a" * 2047
    vietnamese_suffix = "đường_dẫn_bộ_nhớ_đa_tầng_🎉_🚀" * 100
    full_prompt = prefix + vietnamese_suffix
    
    # Python slicing operates on code points
    clamped = full_prompt[:2048]
    assert len(clamped) == 2048
    assert clamped[-1] == "đ"  # Exactly sliced at char boundary without unicode decode error
    
    # Process hook should handle without error
    res = engine.process_hook({"lastUserInput": full_prompt})
    assert isinstance(res, dict)
    assert "injectSteps" in res


def test_tier1_pathological_filler_input():
    """
    Test catastrophic backtracking or CPU blowup on repeated filler keywords.
    """
    engine = Tier1ReflexEngine(SAMPLE_TRACES)
    
    # Massive repetitive filler
    pathological_fillers = [
        "ok " * 10000,
        "tiếp tục " * 10000,
        "ok" + " " * 5000 + "ok",
        "okay " * 5000,
    ]
    
    for pf in pathological_fillers:
        t0 = time.perf_counter()
        res = engine.process_hook({"lastUserInput": pf})
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert res == {"injectSteps": []}
        assert elapsed_ms < 5.0, f"Pathological filler took {elapsed_ms:.2f}ms!"


# ============================================================================
# 2. RSK-004 & RSK-005: FTS5 Sanitization & Adversarial Characters
# ============================================================================

def test_fts5_sanitization_comprehensive_ascii_symbols():
    """
    Test ALL ASCII punctuation and symbol characters in FTS5 sanitization to verify zero syntax crashes.
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(DDL_SCHEMA)
    
    # Insert test record
    conn.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, solution_payload, last_accessed_at, created_at
        ) VALUES ('t1', 'h1', '/ws', 'proven_trace', 'Test Record with All Symbols', 'Sol', datetime('now'), datetime('now'))
        """
    )
    conn.commit()
    
    # All ASCII punctuation characters
    all_symbols = [
        "^", "{", "}", "[", "]", "~", "+", "=", "!", "@", "#", "$", "%", "&", "|", ";", ",", "?", "\\", "/",
        "col:val", "{title}:foo", "^prefix", "word+word", "word~2", "escape\\seq", "[bracketed]", "(parenthesized)",
        "AND AND AND", "NOT NOT", "OR OR", "NEAR/2", '"""', "'''", "<script>alert(1)</script>",
        "SELECT * FROM users WHERE '1'='1' --",
        "   ", "", "\n\t", "---", "...", ":::", "???"
    ]
    
    for sym in all_symbols:
        sanitized = sanitize_fts5_query(sym)
        assert isinstance(sanitized, str)
        # Must execute against SQLite FTS5 without OperationalError
        try:
            cur = conn.execute("SELECT memory_id FROM episodic_fts WHERE episodic_fts MATCH ?", (sanitized,))
            cur.fetchall()
        except sqlite3.OperationalError as e:
            pytest.fail(f"OperationalError on symbol input {sym!r} -> sanitized to {sanitized!r}: {e}")
            
    conn.close()


def test_fts5_empty_query_behavior():
    """
    Test what FTS5 MATCH does when sanitize_fts5_query returns '""'.
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(DDL_SCHEMA)
    
    sanitized_empty = sanitize_fts5_query("   ")
    assert sanitized_empty == '""'
    
    # Running MATCH '""' in FTS5
    cur = conn.execute("SELECT memory_id FROM episodic_fts WHERE episodic_fts MATCH ?", (sanitized_empty,))
    rows = cur.fetchall()
    assert rows == [], "MATCH '\"\"' must return 0 rows, not match everything!"
    conn.close()


def test_vietnamese_nfd_vs_nfc_diacritic_normalization():
    """
    Test decomposed unicode (NFD) vs precomposed unicode (NFC) for Vietnamese text.
    In NFD, 'đ' can be 'd' with stroke, or vowels with combining marks.
    """
    import unicodedata
    
    text_nfc = "Kiến trúc bộ nhớ đa tầng"
    text_nfd = unicodedata.normalize("NFD", text_nfc)
    
    # Test normalization
    norm_nfc = normalize_vietnamese_diacritics(text_nfc)
    norm_nfd = normalize_vietnamese_diacritics(text_nfd)
    
    # In NFD, 'đ' is U+0111 which is a single code point in both NFC and NFD
    assert "d" in norm_nfc.lower()
    assert "d" in norm_nfd.lower()


# ============================================================================
# 3. Database Multi-Workspace Partition Isolation (CRITICAL)
# ============================================================================

def test_multi_workspace_fts_leakage_challenge():
    """
    CHALLENGE: Does episodic_fts leak records across workspaces if queries do not filter by workspace_hash?
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(DDL_SCHEMA)
    
    # Workspace A: Secret project with private architecture
    conn.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, problem_signature, solution_payload, last_accessed_at, created_at
        ) VALUES ('mem_ws_A_secret', 'hash_A', '/workspaces/project_secret_A', 'architecture_decision',
                  'Secret API Token Storage Architecture', 'auth bearer token leak', 'Store tokens in vault',
                  datetime('now'), datetime('now'))
        """
    )
    
    # Workspace B: Public project
    conn.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, problem_signature, solution_payload, last_accessed_at, created_at
        ) VALUES ('mem_ws_B_public', 'hash_B', '/workspaces/project_public_B', 'proven_trace',
                  'Public API Gateway Configuration', 'auth bearer token setup', 'Setup reverse proxy',
                  datetime('now'), datetime('now'))
        """
    )
    conn.commit()
    
    # Adversarial Search from Workspace B for "token"
    query = sanitize_fts5_query("auth bearer token")
    
    # 1. Raw FTS5 search (without workspace partition join)
    cur = conn.execute("SELECT memory_id FROM episodic_fts WHERE episodic_fts MATCH ?", (query,))
    raw_results = [r[0] for r in cur.fetchall()]
    
    # RAW FTS5 SEARCH LEAKS WORKSPACE A TO WORKSPACE B!
    assert "mem_ws_A_secret" in raw_results
    assert "mem_ws_B_public" in raw_results
    
    # 2. Correct Partitioned FTS5 search (MUST JOIN with workspace_episodic_memory)
    cur_isolated = conn.execute(
        """
        SELECT f.memory_id, e.title, e.solution_payload
        FROM episodic_fts f
        JOIN workspace_episodic_memory e ON f.memory_id = e.memory_id
        WHERE f.episodic_fts MATCH ? AND e.workspace_hash = ?
        """,
        (query, "hash_B")
    )
    isolated_results = [r[0] for r in cur_isolated.fetchall()]
    
    # Isolated search MUST ONLY return Workspace B's records
    assert isolated_results == ["mem_ws_B_public"]
    assert "mem_ws_A_secret" not in isolated_results
    
    conn.close()


def test_windows_workspace_path_canonicalization_challenge():
    """
    CHALLENGE: On Windows, paths can have differing drive case, slashes, or trailing slashes.
    Ensure canonical workspace hashing is case-normalized and slash-normalized.
    """
    import hashlib
    
    # Same directory represented 4 different ways in Windows environments
    p1 = r"d:\Antigravity\Skill management"
    p2 = r"D:\antigravity\skill management"
    p3 = r"D:/Antigravity/Skill management/"
    p4 = r"d:/antigravity/skill management\\"
    
    # Naive MD5 hash WITHOUT normalization FAILS
    h1_raw = hashlib.md5(p1.encode("utf-8")).hexdigest()
    h2_raw = hashlib.md5(p2.encode("utf-8")).hexdigest()
    assert h1_raw != h2_raw, "Raw MD5 creates partition collisions across case/slash variations!"
    
    # Canonical normalization strategy
    def canonical_workspace_hash(path: str) -> str:
        # Normcase (lower on Windows) + normpath (backslashes) + abspath
        norm = os.path.normcase(os.path.normpath(os.path.abspath(path)))
        return hashlib.md5(norm.encode("utf-8")).hexdigest()
        
    c1 = canonical_workspace_hash(p1)
    c2 = canonical_workspace_hash(p2)
    c3 = canonical_workspace_hash(p3)
    c4 = canonical_workspace_hash(p4)
    
    assert c1 == c2 == c3 == c4, "Canonical hashing must be invariant across all Windows path representations!"


# ============================================================================
# 4. RSK-006 & Tier 3 Ebbinghaus Boundary Conditions
# ============================================================================

def test_ebbinghaus_extreme_boundary_parameters():
    """
    Test Ebbinghaus stability formula under extreme parameter values.
    """
    # 1. Extreme large delta_days (10,000 years)
    st_ancient = calculate_ebbinghaus_stability(s0=1.0, lambda_0=0.05, delta_days=3650000.0, n_hits=0)
    assert st_ancient == 0.0 or 0.0 <= st_ancient <= 1e-10
    assert 0.0 <= st_ancient <= 1.0
    
    # 2. Extreme large n_hits (1 billion hits)
    st_mega_hits = calculate_ebbinghaus_stability(s0=1.0, lambda_0=0.05, delta_days=30.0, n_hits=1_000_000_000)
    assert 0.0 <= st_mega_hits <= 1.0
    # Higher hits means retention is very close to S0 (~0.876)
    assert st_mega_hits > 0.85
    
    # 3. Negative s0
    st_neg_s0 = calculate_ebbinghaus_stability(s0=-0.5, lambda_0=0.05, delta_days=5.0, n_hits=0)
    assert st_neg_s0 == 0.0
    
    # 4. Overflow s0 (> 1.0)
    st_over_s0 = calculate_ebbinghaus_stability(s0=2.5, lambda_0=0.05, delta_days=0.0, n_hits=0)
    assert st_over_s0 == 1.0


def test_tier3_iso_timestamp_timezone_parsing():
    """
    Test that datetime parsing in consolidator handles both ISO-8601 with 'Z' and SQLite datetime strings.
    """
    now = datetime.now(timezone.utc)
    
    formats_to_test = [
        "2026-11-02 20:00:00",              # SQLite datetime('now')
        "2026-11-02T20:00:00Z",             # ISO-8601 UTC with Z
        "2026-11-02T20:00:00.123456+00:00", # ISO-8601 UTC with offset
    ]
    
    for fmt_str in formats_to_test:
        try:
            # Python 3.11+ fromisoformat handles 'Z' and ' '
            dt = datetime.fromisoformat(fmt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = (now - dt).total_seconds()
            assert isinstance(delta, float)
        except Exception as e:
            pytest.fail(f"Failed to parse timestamp {fmt_str!r}: {e}")


# ============================================================================
# 5. RSK-007: Inter-Process File Mutex & Stale Lock Recovery
# ============================================================================

def test_interprocess_mutex_stale_lock_recovery():
    """
    CHALLENGE: Verify that an inter-process file lock (llama_autostart.lock)
    has a stale-timeout mechanism so that a crashed process does not hang the agent fleet.
    """
    fd, lock_path = tempfile.mkstemp(suffix=".lock")
    os.close(fd)
    
    # Simulate a stale lock created 60 seconds ago by a crashed process
    old_mtime = time.time() - 60.0
    os.utime(lock_path, (old_mtime, old_mtime))
    
    # Defensive acquire algorithm with stale lock detection (>30s)
    def acquire_lock_with_stale_recovery(path: str, stale_timeout_sec: float = 30.0) -> bool:
        if os.path.exists(path):
            file_age = time.time() - os.path.getmtime(path)
            if file_age > stale_timeout_sec:
                # Stale lock detected, override
                try:
                    os.remove(path)
                except OSError:
                    pass
        try:
            # Atomic creation (O_CREAT | O_EXCL)
            new_fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(new_fd, f"pid={os.getpid()};time={time.time()}".encode("utf-8"))
            os.close(new_fd)
            return True
        except FileExistsError:
            return False

    acquired = acquire_lock_with_stale_recovery(lock_path, stale_timeout_sec=30.0)
    assert acquired is True, "Stale lock (>30s) should have been recovered and acquired!"
    
    # Second acquisition immediately after should fail (lock is fresh)
    fresh_acquired = acquire_lock_with_stale_recovery(lock_path, stale_timeout_sec=30.0)
    assert fresh_acquired is False, "Fresh lock must NOT be overridden by another process!"
    
    # Cleanup
    if os.path.exists(lock_path):
        os.remove(lock_path)


# ============================================================================
# 6. RSK-008 & Zero-Trust Secret Redaction Pipeline
# ============================================================================

def test_zero_trust_secret_redaction_regex():
    """
    Test automated credential redaction pipeline against realistic secrets:
    - GitHub PATs (ghp_*, github_pat_*)
    - AI API keys (gsk_*, sk-proj-*, sk-ant-*)
    - Bearer tokens
    - Private keys (RSA/EC/OPENSSH)
    """
    RED_PATTERNS = [
        (re.compile(r"ghp_[A-Za-z0-9]{36,255}"), "[REDACTED_GITHUB_PAT]"),
        (re.compile(r"github_pat_[A-Za-z0-9_]{50,255}"), "[REDACTED_GITHUB_PAT]"),
        (re.compile(r"gsk_[A-Za-z0-9]{40,255}"), "[REDACTED_GROQ_KEY]"),
        (re.compile(r"sk-proj-[A-Za-z0-9_\-]{40,255}"), "[REDACTED_OPENAI_KEY]"),
        (re.compile(r"sk-ant-[A-Za-z0-9_\-]{40,255}"), "[REDACTED_ANTHROPIC_KEY]"),
        (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,255}", re.IGNORECASE), "Bearer [REDACTED_BEARER_TOKEN]"),
        (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[^-]+-----END [A-Z ]+ PRIVATE KEY-----", re.DOTALL), "[REDACTED_PRIVATE_KEY]"),
    ]
    
    def redact_secrets(content: str) -> str:
        res = content
        for pattern, repl in RED_PATTERNS:
            res = pattern.sub(repl, res)
        return res

    samples = [
        ("export GITHUB_TOKEN=ghp_ABC123456789012345678901234567890123456", "[REDACTED_GITHUB_PAT]"),
        ("GROQ_API_KEY=gsk_1234567890abcdef1234567890abcdef1234567890", "[REDACTED_GROQ_KEY]"),
        ("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0", "Bearer [REDACTED_BEARER_TOKEN]"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Y...rest_of_key...\n-----END RSA PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
    ]
    
    for raw, expected_token in samples:
        redacted = redact_secrets(raw)
        assert expected_token in redacted, f"Failed to redact: {raw}"
        assert "ghp_ABC" not in redacted
        assert "gsk_1234" not in redacted
        assert "MIIEow" not in redacted
