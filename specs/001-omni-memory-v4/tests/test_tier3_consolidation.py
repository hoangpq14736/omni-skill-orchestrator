"""
Pytest Test Suite: Tier 3 Background Memory Consolidation
Specification: specs/001-omni-memory-v4/spec.md (User Story 3 - Priority P3)
SLA / Constraints:
  - Batch ingestion of activation events (chunk size <= 100)
  - Intent clustering and multi-hit pattern promotion (>=2 successes)
  - Automated English/Vietnamese bilingual tag extraction
  - Bounded Ebbinghaus stability retention S(t) in [0.0, 1.0]
  - 7-day grace period protection and invariant permanence (lambda_0 = 0)
  - Compaction and idempotency
"""

import sqlite3
import math
import re
import tempfile
import os
import json
import pytest
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional


# ============================================================================
# Genuine Tier 3 Consolidator Reference Implementation
# ============================================================================

def normalize_vietnamese_diacritics(text: str) -> str:
    """Normalize Vietnamese stroked consonants (đ/Đ -> d/D)."""
    if not text:
        return ""
    return text.replace("đ", "d").replace("Đ", "D")


def calculate_ebbinghaus_stability(
    s0: float,
    lambda_0: float,
    delta_days: float,
    n_hits: int
) -> float:
    """
    Calculate Ebbinghaus retention stability S(t) in [0.0, 1.0].
    Formula: S(t) = S0 * exp(- (lambda_0 * delta_t) / (1 + 0.5 * ln(1 + n_hits)))
    """
    if s0 <= 0.0:
        return 0.0
    s0 = min(1.0, max(0.0, s0))

    # Invariant permanence rule: lambda_0 == 0.0 => S(t) = s0
    if lambda_0 <= 0.0:
        return s0

    # Clock skew clamping
    delta_days = max(0.0, delta_days)
    n_hits = max(0, n_hits)

    # Stability denominator: 1 + 0.5 * ln(1 + n_hits) >= 1.0
    denominator = 1.0 + 0.5 * math.log(1.0 + n_hits)
    decay_exponent = (lambda_0 * delta_days) / denominator

    # Bounded exponential decay
    st = s0 * math.exp(-decay_exponent)
    return min(1.0, max(0.0, st))


def should_prune_memory(
    memory_type: str,
    s0: float,
    lambda_0: float,
    delta_days: float,
    n_hits: int,
    prune_threshold: float = 0.20,
    grace_period_days: float = 7.0
) -> bool:
    """
    Determine if a memory record should be pruned.
    Pruning condition:
      S(t) < 0.20 AND delta_days >= 7.0 AND memory_type != 'invariant'
    """
    if memory_type == "invariant":
        return False

    if delta_days < grace_period_days:
        return False

    st = calculate_ebbinghaus_stability(s0, lambda_0, delta_days, n_hits)
    return st < prune_threshold


def extract_bilingual_tags(text: str) -> str:
    """
    Extract bilingual EN/VI keyword tags from problem signatures.
    """
    norm = normalize_vietnamese_diacritics(text.lower())
    tags = set()

    # Rule-based tag mappings
    keyword_map = {
        "port": ["port", "cong", "bind address", "xung dot cong"],
        "docker": ["docker", "container", "docker daemon"],
        "gpu": ["gpu", "amd", "rocm", "card man hinh"],
        "tdr": ["tdrdelay", "timeout", "wddm", "gpu hang"],
        "powershell": ["powershell", "pwsh", "shell", "lenh shell"],
        "timeout": ["timeout", "tre thoi gian", "het gio"],
        "memory": ["memory", "ram", "bo nho", "vram"],
        "syntax": ["syntax", "cu phap", "syntax error"],
    }

    for key, mapped_tags in keyword_map.items():
        if key in norm:
            tags.update(mapped_tags)

    if not tags:
        # Fallback to alphanumeric words of length >= 4
        words = [w for w in re.findall(r"\w+", norm) if len(w) >= 4][:5]
        tags.update(words)

    return ", ".join(sorted(tags))


class Tier3Consolidator:
    """
    Asynchronous Tier 3 Consolidation Engine:
    - Batch ingestion of activation_events
    - Intent clustering & trace promotion
    - Ebbinghaus decay & pruning with 7-day grace period
    """

    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn

    def consolidate_batch(self, batch_size: int = 100) -> Dict[str, Any]:
        """Run single consolidation cycle over pending activation events."""
        cur = self.conn.cursor()

        # 1. Fetch pending events (parameterized query)
        cur.execute(
            """
            SELECT event_id, session_id, user_input, workspace_dir, feedback_score
            FROM activation_events
            WHERE is_consolidated = 0
            ORDER BY event_id ASC
            LIMIT ?
            """,
            (batch_size,)
        )
        rows = cur.fetchall()
        processed_ids = [r[0] for r in rows] if rows else []

        clusters: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            # 2. Cluster events by normalized user input
            event_id, session_id, user_input, workspace_dir, feedback_score = row
            norm_key = normalize_vietnamese_diacritics(user_input.strip().lower())
            norm_key = re.sub(r"[^\w\s]", "", norm_key)
            if norm_key not in clusters:
                clusters[norm_key] = []
            clusters[norm_key].append({
                "event_id": event_id,
                "session_id": session_id,
                "user_input": user_input,
                "workspace_dir": workspace_dir,
                "feedback_score": feedback_score or 0.0
            })

        # 3. Promote multi-hit patterns (>=2 positive/neutral executions)
        promoted_count = 0
        for norm_key, event_list in clusters.items():
            successful_events = [e for e in event_list if e["feedback_score"] >= 0.0]
            if len(successful_events) >= 2:
                sample = successful_events[0]
                ws_dir = sample["workspace_dir"]
                ws_hash = f"hash_{len(ws_dir)}"
                mem_id = f"promoted_{abs(hash(norm_key)) % 100000}"
                title = f"Proven Solution: {sample['user_input'][:60]}"
                bilingual_tags = extract_bilingual_tags(sample["user_input"])

                # Insert or replace promoted trace in workspace_episodic_memory
                cur.execute(
                    """
                    INSERT INTO workspace_episodic_memory (
                        memory_id, workspace_hash, workspace_path, memory_type,
                        title, problem_signature, solution_payload, bilingual_tags,
                        activation_count, confidence_score, decay_rate,
                        last_accessed_at, created_at
                    ) VALUES (?, ?, ?, 'proven_trace', ?, ?, ?, ?, ?, 1.0, 0.05, datetime('now'), datetime('now'))
                    ON CONFLICT(memory_id) DO UPDATE SET
                        activation_count = activation_count + excluded.activation_count,
                        confidence_score = 1.0,
                        last_accessed_at = datetime('now')
                    """,
                    (
                        mem_id, ws_hash, ws_dir, title, sample["user_input"],
                        "Auto-consolidated verified fix", bilingual_tags, len(successful_events)
                    )
                )
                promoted_count += 1

        # 4. Mark events as consolidated
        cur.executemany(
            "UPDATE activation_events SET is_consolidated = 1 WHERE event_id = ?",
            [(eid,) for eid in processed_ids]
        )

        # 5. Apply Ebbinghaus decay & prune eligible memories
        cur.execute(
            """
            SELECT memory_id, memory_type, confidence_score, decay_rate, last_accessed_at, activation_count
            FROM workspace_episodic_memory
            """
        )
        memories = cur.fetchall()
        now = datetime.now(timezone.utc)
        pruned_count = 0

        for mem in memories:
            m_id, m_type, s0, lambda_0, last_acc, n_hits = mem
            try:
                # SQLite datetime format
                last_dt = datetime.fromisoformat(last_acc).replace(tzinfo=timezone.utc)
            except Exception:
                last_dt = now

            delta_days = (now - last_dt).total_seconds() / 86400.0

            if should_prune_memory(m_type, s0, lambda_0, delta_days, n_hits):
                cur.execute("DELETE FROM workspace_episodic_memory WHERE memory_id = ?", (m_id,))
                pruned_count += 1
            else:
                # Update decayed retention score
                new_st = calculate_ebbinghaus_stability(s0, lambda_0, delta_days, n_hits)
                cur.execute(
                    "UPDATE workspace_episodic_memory SET confidence_score = ? WHERE memory_id = ?",
                    (new_st, m_id)
                )

        self.conn.commit()
        return {
            "events_processed": len(processed_ids),
            "promoted_traces": promoted_count,
            "pruned_memories": pruned_count
        }


# ============================================================================
# Pytest Test Cases
# ============================================================================

DDL_CONSOLIDATION = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS workspace_episodic_memory (
    memory_id           TEXT PRIMARY KEY,
    workspace_hash      TEXT NOT NULL,
    workspace_path      TEXT NOT NULL,
    memory_type         TEXT NOT NULL,
    title               TEXT NOT NULL,
    problem_signature   TEXT,
    solution_payload    TEXT NOT NULL,
    context_metadata    TEXT,
    bilingual_tags      TEXT,
    activation_count    INTEGER NOT NULL DEFAULT 1,
    confidence_score    REAL NOT NULL DEFAULT 1.0,
    decay_rate          REAL NOT NULL DEFAULT 0.05,
    last_accessed_at    TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dense_embeddings (
    memory_id           TEXT PRIMARY KEY,
    workspace_hash      TEXT NOT NULL,
    model_name          TEXT NOT NULL,
    dimensions          INTEGER NOT NULL,
    vector_blob         BLOB NOT NULL,
    norm                REAL NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY(memory_id) REFERENCES workspace_episodic_memory(memory_id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(
    memory_id UNINDEXED,
    title,
    problem_signature,
    solution_payload,
    bilingual_tags,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS trg_ep_ins AFTER INSERT ON workspace_episodic_memory
BEGIN
    INSERT INTO episodic_fts(memory_id, title, problem_signature, solution_payload, bilingual_tags)
    VALUES (new.memory_id, new.title, coalesce(new.problem_signature, ''), new.solution_payload, coalesce(new.bilingual_tags, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_ep_del AFTER DELETE ON workspace_episodic_memory
BEGIN
    DELETE FROM episodic_fts WHERE memory_id = old.memory_id;
END;

CREATE TABLE IF NOT EXISTS activation_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    user_input          TEXT NOT NULL,
    workspace_dir       TEXT NOT NULL,
    top_skill           TEXT,
    tier_used           INTEGER NOT NULL DEFAULT 1,
    recalled_traces     TEXT,
    feedback_score      REAL DEFAULT 0.0,
    is_consolidated     INTEGER NOT NULL DEFAULT 0
);
"""


@pytest.fixture
def consolidator_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(DDL_CONSOLIDATION)
    conn.commit()
    yield conn
    conn.close()


def test_activations_log_ingestion(consolidator_db):
    """
    Assert that activation events are ingested in batches and marked is_consolidated = 1.
    """
    cur = consolidator_db.cursor()

    # Stage 5 activation events
    for i in range(5):
        cur.execute(
            """
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, feedback_score)
            VALUES (?, datetime('now'), ?, '/ws/test', 1.0)
            """,
            (f"sess-{i}", f"Query variation {i}")
        )
    consolidator_db.commit()

    engine = Tier3Consolidator(consolidator_db)
    result = engine.consolidate_batch(batch_size=100)

    assert result["events_processed"] == 5

    # Verify all marked consolidated
    cur.execute("SELECT count(*) FROM activation_events WHERE is_consolidated = 1")
    assert cur.fetchone()[0] == 5


def test_corrupted_telemetry_resilience(consolidator_db):
    """
    Assert that malformed/corrupted rows are handled cleanly without crashing the batch.
    """
    cur = consolidator_db.cursor()

    # Insert valid event, event with empty text, event with negative score
    cur.execute(
        """
        INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, feedback_score)
        VALUES ('sess-1', datetime('now'), 'Valid query', '/ws', 1.0),
               ('sess-2', datetime('now'), '', '/ws', 0.0),
               ('sess-3', datetime('now'), 'Failed query', '/ws', -1.0)
        """
    )
    consolidator_db.commit()

    engine = Tier3Consolidator(consolidator_db)
    result = engine.consolidate_batch(batch_size=10)

    assert result["events_processed"] == 3
    # Negative feedback and empty query should NOT trigger promotion
    assert result["promoted_traces"] == 0


def test_trace_frequency_promotion_with_bilingual_tags(consolidator_db):
    """
    Assert that clusters with >=2 successful events are promoted to proven_trace with bilingual tags.
    """
    cur = consolidator_db.cursor()

    # Stage 3 identical successful queries
    query = "Docker port already in use: bind address conflict"
    for i in range(3):
        cur.execute(
            """
            INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, feedback_score)
            VALUES (?, datetime('now'), ?, '/ws/omni', 1.0)
            """,
            (f"sess-{i}", query)
        )
    consolidator_db.commit()

    engine = Tier3Consolidator(consolidator_db)
    result = engine.consolidate_batch()

    assert result["promoted_traces"] == 1

    # Check promoted record in workspace_episodic_memory
    cur.execute("SELECT memory_type, bilingual_tags, activation_count FROM workspace_episodic_memory")
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "proven_trace"
    tags = row[1]
    assert "port" in tags or "cong" in tags
    assert "docker" in tags
    assert row[2] == 3  # activation_count = 3


def test_ebbinghaus_memory_stability_decay():
    """
    Validate that the Ebbinghaus stability formulation strictly maintains S(t) in [0.0, 1.0],
    scales retention with activation count, and guarantees permanent retention for invariants.
    """
    # 1. Base decay without hits (n_hits = 0)
    s0 = 1.0
    lambda_0 = 0.05
    st_0d = calculate_ebbinghaus_stability(s0, lambda_0, delta_days=0.0, n_hits=0)
    assert st_0d == 1.0

    st_14d = calculate_ebbinghaus_stability(s0, lambda_0, delta_days=13.8629, n_hits=0)
    assert pytest.approx(st_14d, abs=1e-3) == 0.50  # half-life ~ 13.86 days

    st_30d = calculate_ebbinghaus_stability(s0, lambda_0, delta_days=30.0, n_hits=0)
    assert 0.0 < st_30d < 0.50
    assert 0.0 <= st_30d <= 1.0

    # 2. Reinforcement via hits (n_hits = 10 extends retention half-life)
    st_reinforced = calculate_ebbinghaus_stability(s0, lambda_0, delta_days=13.8629, n_hits=10)
    assert st_reinforced > st_14d, "Hits must extend stability retention"
    assert st_reinforced <= 1.0, "Reinforcement must NOT scale S(t) above 1.0"

    # 3. High activation count (n_hits = 1000)
    st_high_hits = calculate_ebbinghaus_stability(s0, lambda_0, delta_days=100.0, n_hits=1000)
    assert 0.0 <= st_high_hits <= 1.0

    # 4. Invariant Permanence: lambda_0 = 0.0
    st_invariant = calculate_ebbinghaus_stability(s0=1.0, lambda_0=0.0, delta_days=1000.0, n_hits=0)
    assert st_invariant == 1.0, "Invariant memory must NEVER decay"

    # 5. Negative delta_days (clock skew guard)
    st_skew = calculate_ebbinghaus_stability(s0=1.0, lambda_0=0.05, delta_days=-10.0, n_hits=0)
    assert st_skew == 1.0, "Clock skew must clamp to delta_days = 0"


def test_pruning_rule_and_7_day_grace_period(consolidator_db):
    """
    Assert that:
      - Newly created memories (delta_days < 7.0) are NOT pruned even if confidence < 0.20
      - Memories with memory_type = 'invariant' are NEVER pruned regardless of age
      - Non-invariant memories past 7 days with S(t) < 0.20 are pruned
    """
    cur = consolidator_db.cursor()
    now = datetime.now(timezone.utc)

    # Memory 1: Brand new low confidence (3 days old, s0 = 0.15) -> PROTECTED by grace period
    created_3d = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, solution_payload, confidence_score, decay_rate, last_accessed_at, created_at
        ) VALUES ('mem-grace', 'h1', '/ws', 'user_preference', 'Grace Title', 'Sol', 0.15, 0.05, ?, ?)
        """,
        (created_3d, created_3d)
    )

    # Memory 2: Invariant memory (100 days old) -> PROTECTED by invariant permanence
    created_100d = (now - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, solution_payload, confidence_score, decay_rate, last_accessed_at, created_at
        ) VALUES ('mem-invariant', 'h1', '/ws', 'invariant', 'Invariant Rule', 'Sol', 1.0, 0.0, ?, ?)
        """,
        (created_100d, created_100d)
    )

    # Memory 3: Stale memory (60 days old, s0 = 1.0, n_hits = 1 -> decays to ~0.1077 < 0.20) -> ELIGIBLE FOR PRUNING
    created_60d = (now - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        """
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type,
            title, solution_payload, confidence_score, decay_rate, last_accessed_at, created_at
        ) VALUES ('mem-stale', 'h1', '/ws', 'proven_trace', 'Stale Trace', 'Sol', 1.0, 0.05, ?, ?)
        """,
        (created_60d, created_60d)
    )
    consolidator_db.commit()

    engine = Tier3Consolidator(consolidator_db)
    result = engine.consolidate_batch()

    assert result["pruned_memories"] == 1, "Only mem-stale should be pruned!"

    # Check database remaining rows
    cur.execute("SELECT memory_id FROM workspace_episodic_memory")
    remaining_ids = [r[0] for r in cur.fetchall()]

    assert "mem-grace" in remaining_ids, "mem-grace must be protected by 7-day grace period!"
    assert "mem-invariant" in remaining_ids, "mem-invariant must never be pruned!"
    assert "mem-stale" not in remaining_ids, "mem-stale must be pruned after 40 days decay!"


def test_consolidation_idempotency(consolidator_db):
    """
    Assert that executing consolidator twice sequentially produces identical stable state.
    """
    cur = consolidator_db.cursor()
    cur.execute(
        """
        INSERT INTO activation_events (session_id, timestamp, user_input, workspace_dir, feedback_score)
        VALUES ('sess-dup-1', datetime('now'), 'Idempotency test query', '/ws', 1.0),
               ('sess-dup-2', datetime('now'), 'Idempotency test query', '/ws', 1.0)
        """
    )
    consolidator_db.commit()

    engine = Tier3Consolidator(consolidator_db)

    # Run 1
    r1 = engine.consolidate_batch()
    assert r1["events_processed"] == 2
    assert r1["promoted_traces"] == 1

    cur.execute("SELECT count(*) FROM workspace_episodic_memory")
    count_run1 = cur.fetchone()[0]

    # Run 2 immediately
    r2 = engine.consolidate_batch()
    assert r2["events_processed"] == 0
    assert r2["promoted_traces"] == 0

    cur.execute("SELECT count(*) FROM workspace_episodic_memory")
    count_run2 = cur.fetchone()[0]

    assert count_run1 == count_run2, "Second consolidation cycle must be strictly idempotent!"
