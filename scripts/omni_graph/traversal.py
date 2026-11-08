"""Recursive CTE Graph Traversal & Blast Radius Engine for Omni-Graph (Graphify)."""

from __future__ import annotations

import sqlite3
from typing import List, Dict, Any

class BlastRadiusEngine:
    """Encapsulates recursive CTE queries for callers and callees."""

    _CALLER_CTE = """
    WITH RECURSIVE caller_tree(source_id, target_id, relation_type, depth, path_tokens) AS (
        SELECT
            e.source_id,
            e.target_id,
            e.relation_type,
            1,
            '|' || e.target_id || '|' || e.source_id || '|'
        FROM edges e
        WHERE (e.target_id = ? OR e.target_id LIKE ?)
          AND e.relation_type IN ('calls', 'imports')
        UNION ALL
        SELECT
            e.source_id,
            e.target_id,
            e.relation_type,
            ct.depth + 1,
            ct.path_tokens || e.source_id || '|'
        FROM edges e
        JOIN caller_tree ct ON e.target_id = ct.source_id
        WHERE ct.depth < ?
          AND instr(ct.path_tokens, '|' || e.source_id || '|') = 0
          AND e.relation_type IN ('calls', 'imports')
    )
    SELECT source_id, relation_type, MIN(depth) AS depth
    FROM caller_tree
    GROUP BY source_id, relation_type
    ORDER BY depth ASC;
    """

    _CALLEE_CTE = """
    WITH RECURSIVE callee_tree(source_id, target_id, relation_type, depth, path_tokens) AS (
        SELECT
            e.source_id,
            e.target_id,
            e.relation_type,
            1,
            '|' || e.source_id || '|' || e.target_id || '|'
        FROM edges e
        WHERE (e.source_id = ? OR e.source_id LIKE ?)
          AND e.relation_type IN ('calls', 'imports')
        UNION ALL
        SELECT
            e.source_id,
            e.target_id,
            e.relation_type,
            ct.depth + 1,
            ct.path_tokens || e.target_id || '|'
        FROM edges e
        JOIN callee_tree ct ON e.source_id = ct.target_id
        WHERE ct.depth < ?
          AND instr(ct.path_tokens, '|' || e.target_id || '|') = 0
          AND e.relation_type IN ('calls', 'imports')
    )
    SELECT target_id AS source_id, relation_type, MIN(depth) AS depth
    FROM callee_tree
    GROUP BY target_id, relation_type
    ORDER BY depth ASC;
    """

    @staticmethod
    def _run_query(conn: sqlite3.Connection, sql: str,
                   node: str, max_depth: int) -> List[Dict[str, Any]]:
        pattern = f"%{node}%"
        cur = conn.execute(sql, (node, pattern, max_depth))
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        return rows

    @classmethod
    def query_callers(cls, conn: sqlite3.Connection,
                      target: str, max_depth: int = 4) -> List[Dict[str, Any]]:
        return cls._run_query(conn, cls._CALLER_CTE, target, max_depth)

    @classmethod
    def query_callees(cls, conn: sqlite3.Connection,
                      source: str, max_depth: int = 4) -> List[Dict[str, Any]]:
        return cls._run_query(conn, cls._CALLEE_CTE, source, max_depth)

def query_callers(conn: sqlite3.Connection, target: str, max_depth: int = 4) -> List[Dict[str, Any]]:
    return BlastRadiusEngine.query_callers(conn, target, max_depth)

def query_callees(conn: sqlite3.Connection, source: str, max_depth: int = 4) -> List[Dict[str, Any]]:
    return BlastRadiusEngine.query_callees(conn, source, max_depth)

def compute_blast_radius(conn: sqlite3.Connection, target_or_file: str, max_depth: int = 4) -> Dict[str, Any]:
    callers = query_callers(conn, target_or_file, max_depth)

    direct = [c for c in callers if c["depth"] == 1]
    transitive = [c for c in callers if c["depth"] > 1]

    impacted_files = sorted(list({
        c["source_id"].split(":")[0] if ":" in c["source_id"] else c["source_id"]
        for c in callers
    }))

    score = min(
        100,
        len(direct) * 15 + len(transitive) * 5 + len(impacted_files) * 10,
    )
    if score < 25:
        level = "LOW"
    elif score < 60:
        level = "MEDIUM"
    else:
        level = "CRITICAL"

    summary = (
        f"Target '{target_or_file}' has {len(direct)} direct caller(s) "
        f"and {len(transitive)} transitive caller(s) across {len(impacted_files)} file(s). "
        f"Risk: {level} (score {score}/100)."
    )

    return {
        "target": target_or_file,
        "direct_callers": direct,
        "transitive_callers": transitive,
        "impacted_files": impacted_files,
        "risk_score": score,
        "risk_level": level,
        "summary": summary,
    }
