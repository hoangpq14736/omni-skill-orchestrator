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
        WHERE (e.target_id = ? OR e.target_id LIKE ? OR e.target_id LIKE ?)
          AND e.relation_type IN ('calls', 'imports')
        UNION ALL
        SELECT
            e.source_id,
            e.target_id,
            e.relation_type,
            ct.depth + 1,
            ct.path_tokens || e.source_id || '|'
        FROM edges e
        JOIN caller_tree ct ON (
            e.target_id = ct.source_id
            OR (
                instr(ct.source_id, ':') > 0
                AND instr(ct.source_id, ':module') = 0
                AND instr(ct.source_id, ':package') = 0
                AND (
                    e.target_id = substr(ct.source_id, instr(ct.source_id, ':') + 1)
                    OR e.target_id LIKE '%.' || substr(ct.source_id, instr(ct.source_id, ':') + 1)
                )
            )
        )
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
        WHERE (e.source_id = ? OR e.source_id LIKE ? OR e.source_id LIKE ?)
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
        norm = node.replace("\\", "/")
        is_file_like = "/" in norm or norm.endswith(
            (".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs")
        )
        if is_file_like:
            p1, p2 = f"{norm}:%", f"%/{norm}:%"
            cur = conn.execute(sql, (norm, p1, p2, max_depth))
        else:
            p1, p2 = f"%.{node}", f"%:{node}"
            cur = conn.execute(sql, (node, p1, p2, max_depth))
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


def query_file_callers(conn: sqlite3.Connection, canonical_file_path: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Returns functions/methods/classes in canonical_file_path with their external callers."""
    norm = canonical_file_path.replace("\\", "/").lower()
    stem = norm.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name, qualified_name, line_number
        FROM nodes
        WHERE file_path = ?
          AND node_type IN ('function', 'async_function', 'method', 'async_method', 'class')
        """,
        (norm,),
    )
    defs = cur.fetchall()
    # Files that explicitly import this module stem (filters false collisions on 'main' / '_helper')
    cur.execute(
        "SELECT DISTINCT file_path FROM edges WHERE relation_type = 'imports' AND (target_id = ? OR target_id LIKE ? OR target_id LIKE ?)",
        (stem, f"%.{stem}", f"{stem}.%"),
    )
    importing_files = {r[0] for r in cur.fetchall()}

    results: List[Dict[str, Any]] = []
    for name, qname, lineno in defs:
        is_generic = name == "main" or name.startswith("_")
        cur.execute(
            """
            SELECT DISTINCT source_id, file_path, line_number, target_id
            FROM edges
            WHERE relation_type = 'calls'
              AND file_path != ?
              AND (target_id = ? OR target_id = ? OR target_id LIKE ? OR target_id LIKE ?)
            ORDER BY file_path ASC, line_number ASC
            LIMIT 12
            """,
            (norm, name, qname, f"%.{name}", f"%:{name}"),
        )
        callers = []
        for r in cur.fetchall():
            if is_generic and r[1] not in importing_files and "." not in (r[3] or ""):
                continue
            callers.append({"source_id": r[0], "file_path": r[1], "line_number": r[2]})
        if callers:
            results.append({
                "symbol": name,
                "qualified_name": qname,
                "line_number": lineno,
                "callers": callers,
            })
    cur.close()
    results.sort(key=lambda item: (-len(item["callers"]), item["line_number"]))
    return results[:limit]
