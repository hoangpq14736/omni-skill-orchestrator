"""
Empirical Adversarial Test Harness for Omni-Graph (specs/003-omni-graph/plan.md)
Tests SQLite schema, indexes, EXPLAIN QUERY PLAN, recursive CTE cycle prevention,
substring collision resistance, diamond dependencies, self-loops, cascading deletes,
and execution latency under realistic topologies.
"""

import json
import os
import random
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- DDL Schema from plan.md §4.1, §4.2, §4.3 ---

PRAGMAS_WAL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -8000;
PRAGMA auto_vacuum = INCREMENTAL;
"""

PRAGMAS_MEMORY = """
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
"""

DDL_SCHEMA = """
-- 1. File Metadata Table
CREATE TABLE IF NOT EXISTS codebase_files_meta (
    file_path       TEXT PRIMARY KEY,
    display_path    TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    mtime           REAL NOT NULL,
    size_bytes      INTEGER NOT NULL,
    parsed_at       REAL NOT NULL,
    parse_status    TEXT NOT NULL,
    node_count      INTEGER NOT NULL DEFAULT 0,
    edge_count      INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT
);

-- Backward compatibility view
CREATE VIEW IF NOT EXISTS file_hashes AS SELECT * FROM codebase_files_meta;

-- 2. Nodes Table
CREATE TABLE IF NOT EXISTS nodes (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    qualified_name  TEXT NOT NULL,
    file_path       TEXT NOT NULL REFERENCES codebase_files_meta(file_path) ON DELETE CASCADE,
    display_path    TEXT NOT NULL,
    line_number     INTEGER NOT NULL,
    end_line_number INTEGER NOT NULL,
    node_type       TEXT NOT NULL,
    docstring       TEXT,
    is_exported     BOOLEAN NOT NULL DEFAULT 1
);

-- 3. Signatures Table
CREATE TABLE IF NOT EXISTS signatures (
    node_id             TEXT PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    file_path           TEXT NOT NULL,
    posonly_args        TEXT NOT NULL,
    args                TEXT NOT NULL,
    defaults_count      INTEGER NOT NULL DEFAULT 0,
    vararg              TEXT,
    kwonly_args         TEXT NOT NULL,
    kw_defaults         TEXT NOT NULL,
    kwarg               TEXT,
    return_annotation   TEXT,
    is_async            BOOLEAN NOT NULL DEFAULT 0
);

-- 4. Edges Table
CREATE TABLE IF NOT EXISTS edges (
    source_id           TEXT NOT NULL,
    target_id           TEXT NOT NULL,
    relation_type       TEXT NOT NULL,
    file_path           TEXT NOT NULL REFERENCES codebase_files_meta(file_path) ON DELETE CASCADE,
    line_number         INTEGER NOT NULL,
    call_args_count     INTEGER,
    call_kwargs         TEXT,
    has_splat_pos       BOOLEAN DEFAULT 0,
    has_splat_kw        BOOLEAN DEFAULT 0,
    is_awaited          BOOLEAN DEFAULT 0,
    PRIMARY KEY (source_id, target_id, relation_type, line_number)
);

-- 5. Lifecycle Hooks Table
CREATE TABLE IF NOT EXISTS lifecycle_hooks (
    id                  TEXT PRIMARY KEY,
    hook_name           TEXT NOT NULL,
    handler_node_id     TEXT REFERENCES nodes(id) ON DELETE CASCADE,
    file_path           TEXT NOT NULL,
    line_number         INTEGER NOT NULL,
    registration_style  TEXT NOT NULL,
    priority            INTEGER DEFAULT 100,
    is_registered       BOOLEAN NOT NULL DEFAULT 1
);

-- Indexes from §4.3
CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_edges_tgt_rel ON edges(target_id, relation_type, source_id, line_number);
CREATE INDEX IF NOT EXISTS idx_edges_src_rel ON edges(source_id, relation_type, target_id, line_number);
CREATE INDEX IF NOT EXISTS idx_edges_file ON edges(file_path);
CREATE INDEX IF NOT EXISTS idx_signatures_file ON signatures(file_path);
CREATE INDEX IF NOT EXISTS idx_hooks_name ON lifecycle_hooks(hook_name);
"""

# --- Recursive CTE Queries from plan.md §5.2 & §5.3 ---

SQL_BLAST_RADIUS = """
WITH RECURSIVE blast_radius(node_id, depth, path_tokens, display_chain) AS (
    -- Anchor Member: Direct callers of target node (Depth = 1)
    SELECT 
        e.source_id, 
        1, 
        '|' || ? || '|' || e.source_id || '|',
        e.source_id || ' -> ' || ?
    FROM edges e
    WHERE e.target_id = ? 
      AND e.relation_type IN ('calls', 'imports')
    
    UNION
    
    -- Recursive Member: Transitive callers up to max_depth
    SELECT 
        e.source_id, 
        br.depth + 1, 
        br.path_tokens || e.source_id || '|',
        e.source_id || ' -> ' || br.display_chain
    FROM edges e
    JOIN blast_radius br ON e.target_id = br.node_id
    WHERE e.relation_type IN ('calls', 'imports')
      AND br.depth < ?
      AND instr(br.path_tokens, '|' || e.source_id || '|') = 0
)
SELECT 
    br.node_id, 
    n.name, 
    n.file_path, 
    n.display_path,
    n.line_number, 
    MIN(br.depth) AS shortest_hop_distance,
    br.display_chain AS call_chain
FROM blast_radius br
JOIN nodes n ON br.node_id = n.id
GROUP BY br.node_id
ORDER BY shortest_hop_distance ASC, n.name ASC;
"""

SQL_BLAST_RADIUS_EXCLUDING_TARGET = """
WITH RECURSIVE blast_radius(node_id, depth, path_tokens, display_chain) AS (
    -- Anchor Member: Direct callers of target node
    SELECT 
        e.source_id, 
        1, 
        '|' || ? || '|' || e.source_id || '|',
        e.source_id || ' -> ' || ?
    FROM edges e
    WHERE e.target_id = ? 
      AND e.relation_type IN ('calls', 'imports')
      AND e.source_id != ?
    
    UNION
    
    -- Recursive Member: Transitive callers up to max_depth
    SELECT 
        e.source_id, 
        br.depth + 1, 
        br.path_tokens || e.source_id || '|',
        e.source_id || ' -> ' || br.display_chain
    FROM edges e
    JOIN blast_radius br ON e.target_id = br.node_id
    WHERE e.relation_type IN ('calls', 'imports')
      AND br.depth < ?
      AND instr(br.path_tokens, '|' || e.source_id || '|') = 0
)
SELECT 
    br.node_id, 
    n.name, 
    n.file_path, 
    n.display_path,
    n.line_number, 
    MIN(br.depth) AS shortest_hop_distance,
    br.display_chain AS call_chain
FROM blast_radius br
JOIN nodes n ON br.node_id = n.id
WHERE br.node_id != ?
GROUP BY br.node_id
ORDER BY shortest_hop_distance ASC, n.name ASC;
"""

SQL_BLAST_RADIUS_NAMED = """
WITH RECURSIVE blast_radius(node_id, depth, path_tokens, display_chain) AS (
    SELECT 
        e.source_id, 
        1, 
        '|' || :target_id || '|' || e.source_id || '|',
        e.source_id || ' -> ' || :target_id
    FROM edges e
    WHERE e.target_id = :target_id 
      AND e.relation_type IN ('calls', 'imports')
    
    UNION
    
    SELECT 
        e.source_id, 
        br.depth + 1, 
        br.path_tokens || e.source_id || '|',
        e.source_id || ' -> ' || br.display_chain
    FROM edges e
    JOIN blast_radius br ON e.target_id = br.node_id
    WHERE e.relation_type IN ('calls', 'imports')
      AND br.depth < :max_depth
      AND instr(br.path_tokens, '|' || e.source_id || '|') = 0
)
SELECT 
    br.node_id, 
    n.name, 
    n.file_path, 
    n.display_path,
    n.line_number, 
    MIN(br.depth) AS shortest_hop_distance,
    br.display_chain AS call_chain
FROM blast_radius br
JOIN nodes n ON br.node_id = n.id
GROUP BY br.node_id
ORDER BY shortest_hop_distance ASC, n.name ASC;
"""

SQL_NAIVE_BLAST_RADIUS = """
WITH RECURSIVE blast_radius(node_id, depth, path, display_chain) AS (
    SELECT 
        e.source_id, 
        1, 
        ? || ' -> ' || e.source_id,
        e.source_id || ' -> ' || ?
    FROM edges e
    WHERE e.target_id = ? 
      AND e.relation_type IN ('calls', 'imports')
    
    UNION
    
    SELECT 
        e.source_id, 
        br.depth + 1, 
        br.path || ' -> ' || e.source_id,
        e.source_id || ' -> ' || br.display_chain
    FROM edges e
    JOIN blast_radius br ON e.target_id = br.node_id
    WHERE e.relation_type IN ('calls', 'imports')
      AND br.depth < ?
      AND instr(br.path, e.source_id) = 0
)
SELECT 
    br.node_id, 
    n.name, 
    n.file_path, 
    MIN(br.depth) AS shortest_hop_distance,
    br.display_chain AS call_chain
FROM blast_radius br
JOIN nodes n ON br.node_id = n.id
GROUP BY br.node_id
ORDER BY shortest_hop_distance ASC, n.name ASC;
"""

SQL_CALLEE_TREE = """
WITH RECURSIVE callee_tree(node_id, depth, path_tokens, dependency_chain) AS (
    SELECT 
        e.target_id, 
        1, 
        '|' || ? || '|' || e.target_id || '|',
        ? || ' -> ' || e.target_id
    FROM edges e
    WHERE e.source_id = ? 
      AND e.relation_type IN ('calls', 'imports')
    
    UNION
    
    SELECT 
        e.target_id, 
        ct.depth + 1, 
        ct.path_tokens || e.target_id || '|',
        ct.dependency_chain || ' -> ' || e.target_id
    FROM edges e
    JOIN callee_tree ct ON e.source_id = ct.node_id
    WHERE e.relation_type IN ('calls', 'imports')
      AND ct.depth < ?
      AND instr(ct.path_tokens, '|' || e.target_id || '|') = 0
)
SELECT 
    ct.node_id, 
    n.name, 
    n.file_path, 
    n.display_path,
    MIN(ct.depth) AS shortest_hop_distance,
    ct.dependency_chain
FROM callee_tree ct
JOIN nodes n ON ct.node_id = n.id
GROUP BY ct.node_id
ORDER BY shortest_hop_distance ASC;
"""


def init_database(db_path: str | None = None) -> sqlite3.Connection:
    """Initializes SQLite database with WAL pragmas or in-memory settings."""
    if db_path:
        conn = sqlite3.connect(db_path)
        conn.executescript(PRAGMAS_WAL)
    else:
        conn = sqlite3.connect(":memory:")
        conn.executescript(PRAGMAS_MEMORY)
    conn.executescript(DDL_SCHEMA)
    return conn


# --- Pytest Test Functions ---

def test_schema_creation_and_pragmas():
    """Verify tables, views, columns, foreign keys, and WAL pragmas."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "codebase_graph.db")
        conn = init_database(db_file)
        cur = conn.cursor()

        # Check WAL mode
        cur.execute("PRAGMA journal_mode;")
        journal_mode = cur.fetchone()[0].upper()
        assert journal_mode == "WAL", f"Expected WAL, got {journal_mode}"

        # Check Foreign Keys
        cur.execute("PRAGMA foreign_keys;")
        fk = cur.fetchone()[0]
        assert fk == 1, "Foreign keys must be enabled"

        # Check Synchronous
        cur.execute("PRAGMA synchronous;")
        sync_mode = cur.fetchone()[0]
        # In SQLite: 1 = NORMAL
        assert sync_mode == 1, f"Expected synchronous=1 (NORMAL), got {sync_mode}"

        # Check tables existence
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view');")
        names = {row[0] for row in cur.fetchall()}
        required = {"codebase_files_meta", "file_hashes", "nodes", "signatures", "edges", "lifecycle_hooks"}
        missing = required - names
        assert not missing, f"Missing schema objects: {missing}"

        # Check all 7 indexes
        cur.execute("SELECT name FROM sqlite_master WHERE type = 'index';")
        indexes = {row[0] for row in cur.fetchall()}
        required_indexes = {
            "idx_nodes_file", "idx_nodes_name", "idx_edges_tgt_rel",
            "idx_edges_src_rel", "idx_edges_file", "idx_signatures_file", "idx_hooks_name"
        }
        missing_idx = required_indexes - indexes
        assert not missing_idx, f"Missing indexes: {missing_idx}"
        conn.close()


def test_explain_query_plan_covering_indexes():
    """Verify that EXPLAIN QUERY PLAN uses covering indexes without full table scans."""
    conn = init_database()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO codebase_files_meta VALUES 
        ('f.py', 'f.py', 'hash', 1.0, 100, 1.0, 'SUCCESS', 2, 1, NULL);
    """)
    cur.execute("""
        INSERT INTO nodes VALUES 
        ('f.py:a', 'a', 'f.a', 'f.py', 'f.py', 1, 5, 'function', NULL, 1),
        ('f.py:b', 'b', 'f.b', 'f.py', 'f.py', 6, 10, 'function', NULL, 1);
    """)
    cur.execute("""
        INSERT INTO edges VALUES 
        ('f.py:a', 'f.py:b', 'calls', 'f.py', 8, 0, '[]', 0, 0, 0);
    """)
    conn.commit()

    # Explain blast radius query
    target = 'f.py:b'
    cur.execute(f"EXPLAIN QUERY PLAN {SQL_BLAST_RADIUS}", (target, target, target, 3))
    plan_rows = [row[3] for row in cur.fetchall()]
    plan_text = " | ".join(plan_rows)

    # Must use idx_edges_tgt_rel
    assert "idx_edges_tgt_rel" in plan_text, f"Blast radius did not use idx_edges_tgt_rel: {plan_text}"
    assert "SCAN edges" not in plan_text, f"Unexpected full scan on edges: {plan_text}"

    # Explain callee tree query
    cur.execute(f"EXPLAIN QUERY PLAN {SQL_CALLEE_TREE}", (target, target, target, 3))
    callee_plan = " | ".join(row[3] for row in cur.fetchall())
    assert "idx_edges_src_rel" in callee_plan, f"Callee tree did not use idx_edges_src_rel: {callee_plan}"
    conn.close()


def test_linear_call_chain_traversal():
    """Verify linear call chain A -> B -> C -> D."""
    conn = init_database()
    cur = conn.cursor()

    cur.execute("INSERT INTO codebase_files_meta VALUES ('f.py', 'f.py', 'h', 1.0, 100, 1.0, 'SUCCESS', 4, 3, NULL)")
    nodes = [('f:A', 'A'), ('f:B', 'B'), ('f:C', 'C'), ('f:D', 'D')]
    for nid, name in nodes:
        cur.execute("INSERT INTO nodes VALUES (?, ?, ?, 'f.py', 'f.py', 1, 10, 'function', NULL, 1)", (nid, name, f"f.{name}"))

    edges = [('f:A', 'f:B'), ('f:B', 'f:C'), ('f:C', 'f:D')]
    for src, tgt in edges:
        cur.execute("INSERT INTO edges VALUES (?, ?, 'calls', 'f.py', 5, 0, '[]', 0, 0, 0)", (src, tgt))
    conn.commit()

    target = 'f:D'
    cur.execute(SQL_BLAST_RADIUS, (target, target, target, 3))
    results = cur.fetchall()

    res_dict = {row[0]: (row[5], row[6]) for row in results}
    assert len(res_dict) == 3
    assert res_dict['f:C'][0] == 1
    assert res_dict['f:B'][0] == 2
    assert res_dict['f:A'][0] == 3

    assert "f:C -> f:D" in res_dict['f:C'][1]
    assert "f:B -> f:C -> f:D" in res_dict['f:B'][1]
    assert "f:A -> f:B -> f:C -> f:D" in res_dict['f:A'][1]
    conn.close()


def test_diamond_dependency_and_shortest_hop():
    """
    Diamond graph:
    A -> B -> D
    A -> C -> D
    Both B and C call D. A calls both B and C.
    Blast radius of D should find B (1), C (1), and A (2).
    A must be deduplicated by GROUP BY with shortest hop 2.
    """
    conn = init_database()
    cur = conn.cursor()

    cur.execute("INSERT INTO codebase_files_meta VALUES ('f.py', 'f.py', 'h', 1.0, 100, 1.0, 'SUCCESS', 4, 4, NULL)")
    for nid, name in [('f:A', 'A'), ('f:B', 'B'), ('f:C', 'C'), ('f:D', 'D')]:
        cur.execute("INSERT INTO nodes VALUES (?, ?, ?, 'f.py', 'f.py', 1, 10, 'function', NULL, 1)", (nid, name, f"f.{name}"))

    cur.execute("INSERT INTO edges VALUES ('f:B', 'f:D', 'calls', 'f.py', 1, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:C', 'f:D', 'calls', 'f.py', 2, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:A', 'f:B', 'calls', 'f.py', 3, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:A', 'f:C', 'calls', 'f.py', 4, 0, '[]', 0, 0, 0)")
    conn.commit()

    target = 'f:D'
    cur.execute(SQL_BLAST_RADIUS, (target, target, target, 4))
    results = cur.fetchall()

    res_dict = {row[0]: row[5] for row in results}
    assert len(res_dict) == 3, f"Expected 3 callers, got {len(res_dict)}"
    assert res_dict['f:B'] == 1
    assert res_dict['f:C'] == 1
    assert res_dict['f:A'] == 2, f"Expected shortest hop 2 for A, got {res_dict['f:A']}"
    conn.close()


def test_asymmetric_diamond_shortest_hop_aggregation():
    """
    Asymmetric Diamond:
    A -> D (direct call, depth 1)
    A -> B -> D (indirect call, depth 2)
    Blast radius of D: A must resolve to shortest_hop_distance = 1.
    """
    conn = init_database()
    cur = conn.cursor()

    cur.execute("INSERT INTO codebase_files_meta VALUES ('f.py', 'f.py', 'h', 1.0, 100, 1.0, 'SUCCESS', 3, 3, NULL)")
    for nid, name in [('f:A', 'A'), ('f:B', 'B'), ('f:D', 'D')]:
        cur.execute("INSERT INTO nodes VALUES (?, ?, ?, 'f.py', 'f.py', 1, 10, 'function', NULL, 1)", (nid, name, f"f.{name}"))

    cur.execute("INSERT INTO edges VALUES ('f:A', 'f:D', 'calls', 'f.py', 1, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:B', 'f:D', 'calls', 'f.py', 2, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:A', 'f:B', 'calls', 'f.py', 3, 0, '[]', 0, 0, 0)")
    conn.commit()

    target = 'f:D'
    cur.execute(SQL_BLAST_RADIUS, (target, target, target, 3))
    results = cur.fetchall()

    res_dict = {row[0]: (row[5], row[6]) for row in results}
    assert res_dict['f:A'][0] == 1, f"Expected hop 1 for A, got {res_dict['f:A'][0]}"
    assert res_dict['f:B'][0] == 1
    conn.close()


def test_mutual_recursion_cycle_termination():
    """
    Mutual recursion:
    A -> B -> A
    X -> A (external caller)
    Blast radius of A must terminate cleanly without recursion error.
    """
    conn = init_database()
    cur = conn.cursor()

    cur.execute("INSERT INTO codebase_files_meta VALUES ('f.py', 'f.py', 'h', 1.0, 100, 1.0, 'SUCCESS', 3, 3, NULL)")
    for nid, name in [('f:A', 'A'), ('f:B', 'B'), ('f:X', 'X')]:
        cur.execute("INSERT INTO nodes VALUES (?, ?, ?, 'f.py', 'f.py', 1, 10, 'function', NULL, 1)", (nid, name, f"f.{name}"))

    cur.execute("INSERT INTO edges VALUES ('f:A', 'f:B', 'calls', 'f.py', 1, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:B', 'f:A', 'calls', 'f.py', 2, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:X', 'f:A', 'calls', 'f.py', 3, 0, '[]', 0, 0, 0)")
    conn.commit()

    target = 'f:A'
    cur.execute(SQL_BLAST_RADIUS, (target, target, target, 5))
    results = cur.fetchall()

    res_dict = {row[0]: row[5] for row in results}
    assert 'f:B' in res_dict
    assert 'f:X' in res_dict
    assert res_dict['f:B'] == 1
    assert res_dict['f:X'] == 1
    assert 'f:A' not in res_dict, "Target node A should not be in its own blast radius when called transitively"
    conn.close()


def test_3_node_cycle_termination():
    """Cycle: A -> B -> C -> A."""
    conn = init_database()
    cur = conn.cursor()

    cur.execute("INSERT INTO codebase_files_meta VALUES ('f.py', 'f.py', 'h', 1.0, 100, 1.0, 'SUCCESS', 3, 3, NULL)")
    for nid in ['f:A', 'f:B', 'f:C']:
        cur.execute("INSERT INTO nodes VALUES (?, ?, ?, 'f.py', 'f.py', 1, 10, 'function', NULL, 1)", (nid, nid, nid))

    cur.execute("INSERT INTO edges VALUES ('f:A', 'f:B', 'calls', 'f.py', 1, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:B', 'f:C', 'calls', 'f.py', 2, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:C', 'f:A', 'calls', 'f.py', 3, 0, '[]', 0, 0, 0)")
    conn.commit()

    target = 'f:A'
    cur.execute(SQL_BLAST_RADIUS, (target, target, target, 10))
    results = cur.fetchall()

    res_dict = {row[0]: row[5] for row in results}
    assert len(res_dict) == 2
    assert res_dict['f:C'] == 1
    assert res_dict['f:B'] == 2
    assert 'f:A' not in res_dict
    conn.close()


def test_self_loop_behavior_and_empirical_finding():
    """
    Self-loop: S calls S (recursive function).
    Tests both raw plan.md query behavior and the corrected excluding query.
    """
    conn = init_database()
    cur = conn.cursor()

    cur.execute("INSERT INTO codebase_files_meta VALUES ('f.py', 'f.py', 'h', 1.0, 100, 1.0, 'SUCCESS', 2, 2, NULL)")
    cur.execute("INSERT INTO nodes VALUES ('f:S', 'S', 'f.S', 'f.py', 'f.py', 1, 10, 'function', NULL, 1)")
    cur.execute("INSERT INTO nodes VALUES ('f:Caller', 'Caller', 'f.Caller', 'f.py', 'f.py', 11, 20, 'function', NULL, 1)")

    cur.execute("INSERT INTO edges VALUES ('f:S', 'f:S', 'calls', 'f.py', 5, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:Caller', 'f:S', 'calls', 'f.py', 15, 0, '[]', 0, 0, 0)")
    conn.commit()

    target = 'f:S'

    # Raw query from plan.md:
    cur.execute(SQL_BLAST_RADIUS, (target, target, target, 5))
    raw_results = cur.fetchall()
    raw_dict = {row[0]: row[5] for row in raw_results}

    # EMPIRICAL OBSERVATION:
    # Under raw query, S terminates cleanly (no infinite loop) because path_tokens has |f:S|f:S|.
    # BUT S is included in raw_dict because the anchor member selected e.source_id WHERE e.target_id = ?
    # without checking e.source_id != target!
    assert 'f:S' in raw_dict, "EMPIRICAL FINDING: Raw query includes S in its own blast radius when S is self-recursive"
    assert raw_dict['f:Caller'] == 1

    # Corrected query excluding target:
    cur.execute(SQL_BLAST_RADIUS_EXCLUDING_TARGET, (target, target, target, target, 5, target))
    corrected_results = cur.fetchall()
    corrected_dict = {row[0]: row[5] for row in corrected_results}

    assert 'f:S' not in corrected_dict, "Corrected query excludes S"
    assert corrected_dict['f:Caller'] == 1
    conn.close()


def test_substring_collision_resistance():
    """
    Adversarial test demonstrating failure of naive substring search
    and success of delimiter-safe token isolation.
    """
    conn = init_database()
    cur = conn.cursor()

    files = ['scripts/auth.py', 'scripts/db.py', 'scripts/app.py']
    for f in files:
        cur.execute("INSERT INTO codebase_files_meta VALUES (?, ?, 'h', 1.0, 100, 1.0, 'SUCCESS', 1, 1, NULL)", (f, f))

    n_target = 'scripts/db.py:query'
    n_long = 'scripts/auth.py:verify_token'
    n_short = 'scripts/auth.py:verify'
    n_client = 'scripts/app.py:main'

    for nid, name, f in [(n_target, 'query', 'scripts/db.py'),
                         (n_long, 'verify_token', 'scripts/auth.py'),
                         (n_short, 'verify', 'scripts/auth.py'),
                         (n_client, 'main', 'scripts/app.py')]:
        cur.execute("INSERT INTO nodes VALUES (?, ?, ?, ?, ?, 1, 10, 'function', NULL, 1)", (nid, name, name, f, f))

    cur.execute("INSERT INTO edges VALUES (?, ?, 'calls', ?, 1, 0, '[]', 0, 0, 0)", (n_long, n_target, 'scripts/auth.py'))
    cur.execute("INSERT INTO edges VALUES (?, ?, 'calls', ?, 2, 0, '[]', 0, 0, 0)", (n_short, n_long, 'scripts/auth.py'))
    cur.execute("INSERT INTO edges VALUES (?, ?, 'calls', ?, 3, 0, '[]', 0, 0, 0)", (n_client, n_short, 'scripts/app.py'))
    conn.commit()

    # 1. Run Delimiter Query (from plan.md)
    cur.execute(SQL_BLAST_RADIUS, (n_target, n_target, n_target, 5))
    delim_results = {row[0]: row[5] for row in cur.fetchall()}

    assert n_long in delim_results, "verify_token must be found"
    assert n_short in delim_results, "verify must be found by delimiter query"
    assert n_client in delim_results, "main must be found by delimiter query"
    assert delim_results[n_long] == 1
    assert delim_results[n_short] == 2
    assert delim_results[n_client] == 3

    # 2. Run Naive Query (without delimiters)
    cur.execute(SQL_NAIVE_BLAST_RADIUS, (n_target, n_target, n_target, 5))
    naive_results = {row[0]: row[3] for row in cur.fetchall()}

    # EMPIRICAL PROOF: Naive query misses verify and main because 'verify' is substring of 'verify_token'!
    assert n_long in naive_results
    assert n_short not in naive_results, "EMPIRICAL PROOF: Naive check suffered false cycle collision on 'verify'"
    assert n_client not in naive_results, "EMPIRICAL PROOF: Naive check dropped downstream caller 'main'"
    conn.close()


def test_cascading_deletes_and_orphan_sweep():
    """
    Test ON DELETE CASCADE and orphan edge sweep routine (§8.6).
    """
    conn = init_database()
    cur = conn.cursor()

    cur.execute("INSERT INTO codebase_files_meta VALUES ('mod_a.py', 'mod_a.py', 'h1', 1.0, 100, 1.0, 'SUCCESS', 2, 1, NULL)")
    cur.execute("INSERT INTO codebase_files_meta VALUES ('mod_b.py', 'mod_b.py', 'h2', 1.0, 100, 1.0, 'SUCCESS', 1, 1, NULL)")

    cur.execute("INSERT INTO nodes VALUES ('mod_a.py:f1', 'f1', 'mod_a.f1', 'mod_a.py', 'mod_a.py', 1, 5, 'function', NULL, 1)")
    cur.execute("INSERT INTO nodes VALUES ('mod_a.py:f2', 'f2', 'mod_a.f2', 'mod_a.py', 'mod_a.py', 6, 10, 'function', NULL, 1)")
    cur.execute("INSERT INTO nodes VALUES ('mod_b.py:g1', 'g1', 'mod_b.g1', 'mod_b.py', 'mod_b.py', 1, 5, 'function', NULL, 1)")

    cur.execute("INSERT INTO signatures VALUES ('mod_a.py:f1', 'mod_a.py', '[]', '[]', 0, NULL, '[]', '[]', NULL, NULL, 0)")
    cur.execute("INSERT INTO lifecycle_hooks VALUES ('hook:1', 'pre', 'mod_a.py:f1', 'mod_a.py', 1, 'decorator', 10, 1)")

    cur.execute("INSERT INTO edges VALUES ('mod_a.py:f1', 'mod_b.py:g1', 'calls', 'mod_a.py', 3, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('mod_b.py:g1', 'mod_a.py:f2', 'calls', 'mod_b.py', 3, 0, '[]', 0, 0, 0)")
    conn.commit()

    cur.execute("DELETE FROM codebase_files_meta WHERE file_path = 'mod_a.py'")
    conn.commit()

    cur.execute("SELECT count(*) FROM nodes WHERE file_path = 'mod_a.py'")
    assert cur.fetchone()[0] == 0

    cur.execute("SELECT count(*) FROM signatures WHERE file_path = 'mod_a.py'")
    assert cur.fetchone()[0] == 0

    cur.execute("SELECT count(*) FROM lifecycle_hooks WHERE file_path = 'mod_a.py'")
    assert cur.fetchone()[0] == 0

    cur.execute("SELECT count(*) FROM edges WHERE file_path = 'mod_a.py'")
    assert cur.fetchone()[0] == 0

    cur.execute("SELECT count(*) FROM edges WHERE target_id = 'mod_a.py:f2'")
    assert cur.fetchone()[0] == 1, "Dangling target edge exists before sweep"

    # Run Orphan Sweep Routine (§8.6)
    cur.execute("""
        DELETE FROM edges 
        WHERE source_id NOT IN (SELECT id FROM nodes) 
           OR (target_id LIKE '%:%' AND target_id NOT IN (SELECT id FROM nodes));
    """)
    conn.commit()

    cur.execute("SELECT count(*) FROM edges WHERE target_id = 'mod_a.py:f2'")
    assert cur.fetchone()[0] == 0, "Orphan sweep routine successfully purged dangling target edge"
    conn.close()


def test_forward_callee_tree():
    """Verify Forward Callee Tree query (§5.3)."""
    conn = init_database()
    cur = conn.cursor()

    cur.execute("INSERT INTO codebase_files_meta VALUES ('f.py', 'f.py', 'h', 1.0, 100, 1.0, 'SUCCESS', 4, 3, NULL)")
    for nid in ['f:Root', 'f:Service', 'f:Repo', 'f:DB']:
        cur.execute("INSERT INTO nodes VALUES (?, ?, ?, 'f.py', 'f.py', 1, 10, 'function', NULL, 1)", (nid, nid, nid))

    cur.execute("INSERT INTO edges VALUES ('f:Root', 'f:Service', 'calls', 'f.py', 1, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:Service', 'f:Repo', 'calls', 'f.py', 2, 0, '[]', 0, 0, 0)")
    cur.execute("INSERT INTO edges VALUES ('f:Repo', 'f:DB', 'calls', 'f.py', 3, 0, '[]', 0, 0, 0)")
    conn.commit()

    target = 'f:Root'
    cur.execute(SQL_CALLEE_TREE, (target, target, target, 5))
    results = cur.fetchall()

    res_dict = {row[0]: row[4] for row in results}
    assert len(res_dict) == 3
    assert res_dict['f:Service'] == 1
    assert res_dict['f:Repo'] == 2
    assert res_dict['f:DB'] == 3
    conn.close()


def test_named_parameter_binding():
    """Verify that named parameter query eliminates 4x positional binding friction."""
    conn = init_database()
    cur = conn.cursor()
    cur.execute("INSERT INTO codebase_files_meta VALUES ('f.py', 'f.py', 'h', 1.0, 100, 1.0, 'SUCCESS', 2, 1, NULL)")
    cur.execute("INSERT INTO nodes VALUES ('f:A', 'A', 'f.A', 'f.py', 'f.py', 1, 5, 'function', NULL, 1)")
    cur.execute("INSERT INTO nodes VALUES ('f:B', 'B', 'f.B', 'f.py', 'f.py', 6, 10, 'function', NULL, 1)")
    cur.execute("INSERT INTO edges VALUES ('f:A', 'f:B', 'calls', 'f.py', 8, 0, '[]', 0, 0, 0)")
    conn.commit()

    cur.execute(SQL_BLAST_RADIUS_NAMED, {"target_id": "f:B", "max_depth": 3})
    results = cur.fetchall()
    assert len(results) == 1
    assert results[0][0] == 'f:A'
    assert results[0][5] == 1
    conn.close()


def generate_hierarchical_graph(num_files: int = 50, funcs_per_file: int = 20, seed: int = 42):
    """Generates realistic modular codebase topology (layered DAG with ~1000 nodes)."""
    random.seed(seed)
    num_nodes = num_files * funcs_per_file
    files = [f"pkg/sub_{i//10}/mod_{i}.py" for i in range(num_files)]
    nodes = []
    edges = []

    for i in range(num_nodes):
        f = files[i // funcs_per_file]
        name = f"func_{i % funcs_per_file}"
        nid = f"{f}:{name}"
        nodes.append((nid, name, f"mod_{i//funcs_per_file}.{name}", f, f, 1, 10, 'function', None, 1))

    created = set()
    for i in range(num_nodes):
        f_idx = i // funcs_per_file
        num_calls = random.choices([1, 2, 3, 4], weights=[0.4, 0.35, 0.15, 0.10])[0]
        for _ in range(num_calls):
            r = random.random()
            if r < 0.85 and (i % funcs_per_file) > 0:
                # Local intra-module call
                target_idx = f_idx * funcs_per_file + random.randint(0, (i % funcs_per_file) - 1)
            elif r < 0.98 and f_idx > 0:
                # Layered cross-module call
                prev_f = random.randint(0, f_idx - 1)
                target_idx = prev_f * funcs_per_file + random.randint(0, funcs_per_file - 1)
            else:
                # Core shared utility call
                target_idx = random.randint(0, min(funcs_per_file - 1, num_nodes - 1))
            
            src = nodes[i][0]
            tgt = nodes[target_idx][0]
            if src != tgt and (src, tgt) not in created:
                created.add((src, tgt))
                edges.append((src, tgt, 'calls', nodes[i][3], 10, 0, '[]', 0, 0, 0))

    return files, nodes, edges


def benchmark_hierarchical_scale(num_files: int = 50, funcs_per_file: int = 20, iterations: int = 100, max_depth: int = 3):
    """Benchmarks query execution latency on hierarchical DAG under WAL mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "hierarchical_bench.db")
        conn = init_database(db_path)
        cur = conn.cursor()

        files, nodes, edges = generate_hierarchical_graph(num_files, funcs_per_file, seed=123)

        file_rows = [(f, f, "sha256", 1.0, 1000, 1.0, 'SUCCESS', funcs_per_file, len(edges)//num_files, None) for f in files]
        cur.executemany("INSERT INTO codebase_files_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", file_rows)
        cur.executemany("INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", nodes)
        cur.executemany("INSERT INTO edges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", edges)
        conn.commit()

        sample_targets = random.sample([n[0] for n in nodes], min(iterations, len(nodes)))

        latencies_ms = []
        result_sizes = []

        for tgt in sample_targets:
            t0 = time.perf_counter()
            cur.execute(SQL_BLAST_RADIUS, (tgt, tgt, tgt, max_depth))
            rows = cur.fetchall()
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)
            result_sizes.append(len(rows))

        latencies_ms.sort()
        p50 = latencies_ms[int(len(latencies_ms) * 0.50)]
        p90 = latencies_ms[int(len(latencies_ms) * 0.90)]
        p99 = latencies_ms[min(int(len(latencies_ms) * 0.99), len(latencies_ms) - 1)]
        max_lat = max(latencies_ms)
        avg_lat = sum(latencies_ms) / len(latencies_ms)
        avg_size = sum(result_sizes) / len(result_sizes)

        conn.close()
        return {
            "num_nodes": len(nodes),
            "num_edges": len(edges),
            "iterations": iterations,
            "max_depth": max_depth,
            "p50_ms": p50,
            "p90_ms": p90,
            "p99_ms": p99,
            "max_ms": max_lat,
            "avg_ms": avg_lat,
            "avg_result_size": avg_size
        }


def test_scale_benchmark_hierarchical_codebase():
    """Verify latency SLA (<0.30ms P50, <1.0ms P99) on 1,000 nodes realistic modular codebase at depth 3."""
    bench = benchmark_hierarchical_scale(num_files=50, funcs_per_file=20, iterations=100, max_depth=3)
    print("\n[BENCHMARK HIERARCHICAL CODEBASE (1,000 NODES / ~1,800 EDGES) AT DEPTH 3]")
    print(f"P50: {bench['p50_ms']:.4f} ms | P90: {bench['p90_ms']:.4f} ms | P99: {bench['p99_ms']:.4f} ms | Max: {bench['max_ms']:.4f} ms")
    print(f"Avg reachable callers: {bench['avg_result_size']:.1f}")

    assert bench['p50_ms'] < 0.30, f"P50 exceeded 0.30ms: {bench['p50_ms']:.4f} ms"
    assert bench['p99_ms'] < 1.00, f"P99 exceeded 1.00ms: {bench['p99_ms']:.4f} ms"


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING OMNI-GRAPH EMPIRICAL ADVERSARIAL TEST HARNESS")
    print("=" * 70)

    print("1. Running Schema & PRAGMA Verification...")
    test_schema_creation_and_pragmas()
    print("   -> PASS: WAL mode, foreign keys, tables, and 7 indexes verified.")

    print("2. Running EXPLAIN QUERY PLAN Covering Index Check...")
    test_explain_query_plan_covering_indexes()
    print("   -> PASS: idx_edges_tgt_rel and idx_edges_src_rel covering indexes verified.")

    print("3. Running Linear Call Chain Traversal...")
    test_linear_call_chain_traversal()
    print("   -> PASS: Linear hops A -> B -> C -> D correctly computed.")

    print("4. Running Diamond Dependency & Shortest Hop...")
    test_diamond_dependency_and_shortest_hop()
    print("   -> PASS: Diamond paths deduplicated with MIN(depth)=2.")

    print("5. Running Asymmetric Diamond Shortest Hop Aggregation...")
    test_asymmetric_diamond_shortest_hop_aggregation()
    print("   -> PASS: Asymmetric paths correctly aggregate to shortest hop distance 1.")

    print("6. Running Mutual Recursion Cycle Termination (A -> B -> A)...")
    test_mutual_recursion_cycle_termination()
    print("   -> PASS: Mutual recursion cleanly terminates without infinite loop.")

    print("7. Running 3-Node Cycle Termination (A -> B -> C -> A)...")
    test_3_node_cycle_termination()
    print("   -> PASS: 3-Node cycle cleanly terminates.")

    print("8. Running Self-Loop (S -> S) Behavior Test...")
    test_self_loop_behavior_and_empirical_finding()
    print("   -> PASS: Self-loop behavior verified and documented.")

    print("9. Running Substring Collision Resistance Test (Naive vs Delimiter)...")
    test_substring_collision_resistance()
    print("   -> PASS: Substring collision proven: Naive DROPS nodes; Delimiter RETAINS nodes.")

    print("10. Running Cascading Deletes & Orphan Edge Sweep...")
    test_cascading_deletes_and_orphan_sweep()
    print("   -> PASS: ON DELETE CASCADE and orphan sweep routine verified.")

    print("11. Running Forward Callee Tree Test...")
    test_forward_callee_tree()
    print("   -> PASS: Callee tree correctly traversed.")

    print("12. Running Named Parameter Binding Test...")
    test_named_parameter_binding()
    print("   -> PASS: Named parameter binding verified.")

    print("13. Running Scale Benchmark: Hierarchical Codebase (1,000 Nodes / ~1,800 Edges, Depth 3)...")
    test_scale_benchmark_hierarchical_codebase()
    print("   -> PASS: Sub-millisecond SLA verified on realistic software topology.")

    print("\n" + "=" * 70)
    print("ALL 13 EMPIRICAL TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)
