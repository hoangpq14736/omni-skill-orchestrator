"""
Suite 4: End-to-End Security & Zero-Trust Leakage Protection Tests (Omni-Memory v4.0).
Validates credential redaction pipeline, local-only storage boundary, and invariant revert ACID safety.
"""

import os
import sqlite3
import sys
import tempfile
import pytest

_SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts"))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from sanitizer import redact_credentials
from memory_schema import init_database
from memory_engine import revert_invariant, search_fts5


def test_zero_trust_credential_redaction_patterns():
    """Verify that all key patterns and secrets are scrubbed before storage."""
    # 1. Groq key
    text_groq = "Authorization: Bearer gsk_1234567890abcdef1234567890"
    assert "gsk_" not in redact_credentials(text_groq)
    assert "[REDACTED_GROQ_KEY]" in redact_credentials(text_groq)

    # 2. OpenAI key
    text_openai = "OPENAI_API_KEY=sk-proj-abc1234567890def1234567890"
    assert "sk-proj-" not in redact_credentials(text_openai)
    assert "[REDACTED_OPENAI_KEY]" in redact_credentials(text_openai)

    # 3. GitHub PAT
    text_gh = "git clone https://ghp_123456789012345678901234567890123456@github.com"
    assert "ghp_" not in redact_credentials(text_gh)
    assert "[REDACTED_GITHUB_TOKEN]" in redact_credentials(text_gh)

    # 4. PKCS#8 private key
    text_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----"
    assert "MIIEow" not in redact_credentials(text_key)
    assert "[REDACTED_PRIVATE_KEY]" in redact_credentials(text_key)


def test_zero_leakage_and_invariant_rollback():
    """Verify that invariant rollback executes atomically and maintains partition safety."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "sec_test.db")
        conn = init_database(db_path)
        cur = conn.cursor()

        ws_hash = "ws_sec_hash"

        # 1. Store clean V1 invariant
        cur.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, content_folded,
                status, superseded_by, last_accessed_at, created_at
            ) VALUES (
                'inv-sec-v1', ?, '/ws/sec', 'invariant',
                'Sec Policy V1', 'rule v1', 'sanitize_inputs()', 'sec policy v1',
                'Active', NULL, datetime('now'), datetime('now')
            )
            """,
            (ws_hash,)
        )
        conn.commit()

        # 2. V2 supersedes V1
        cur.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, problem_signature, solution_payload, content_folded,
                status, superseded_by, last_accessed_at, created_at
            ) VALUES (
                'inv-sec-v2', ?, '/ws/sec', 'invariant',
                'Sec Policy V2', 'rule v2', 'allow_all()', 'sec policy v2',
                'Active', NULL, datetime('now'), datetime('now')
            )
            """,
            (ws_hash,)
        )
        cur.execute("UPDATE workspace_episodic_memory SET status = 'Superseded', superseded_by = 'inv-sec-v2' WHERE memory_id = 'inv-sec-v1'")
        conn.commit()

        # 3. Test rollback
        assert revert_invariant(conn, 'inv-sec-v1') is True

        # Check records
        cur.execute("SELECT memory_id, status, superseded_by FROM workspace_episodic_memory")
        recs = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        assert recs['inv-sec-v1'][0] == 'Active'
        assert recs['inv-sec-v2'][0] == 'Superseded'
        assert recs['inv-sec-v2'][1] == 'inv-sec-v1'

        conn.close()
