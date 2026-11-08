"""Post-edit micro-indexing and self-healing hook for Omni-Graph."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, Union

from .storage import (
    get_connection,
    delete_file_records,
    batch_insert_nodes,
    batch_insert_signatures,
    batch_insert_edges,
    batch_insert_lifecycle_hooks,
    record_file_parsed,
)
from .fingerprint import normalize_canonical_path, compute_sha256, DEFAULT_SUPPORTED_EXTENSIONS
from .visitor import parse_source_file, parse_python_file

def micro_index_file(workspace_root: Union[str, Path], file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Incrementally re-indexes a single file upon edit/write in < 10ms.
    Guarantees atomic update and eliminates stale graph entries.
    Supports all polyglot files recognized by Omni-Graph.
    """
    root = Path(workspace_root).resolve()
    target = Path(file_path)
    abs_path = target if target.is_absolute() else (root / target)

    if not abs_path.exists():
        # File was deleted: purge records
        canon, _ = normalize_canonical_path(root, abs_path)
        try:
            conn = get_connection(root, read_only=False, timeout_ms=2000)
            delete_file_records(conn, canon)
            conn.close()
            return {"file_path": canon, "status": "DELETED", "node_count": 0, "edge_count": 0}
        except Exception as exc:
            return {"file_path": canon, "status": "ERROR", "error": str(exc)}

    canon, display = normalize_canonical_path(root, abs_path)
    suffix = Path(canon).suffix.lower()
    if suffix not in DEFAULT_SUPPORTED_EXTENSIONS:
        return {"file_path": canon, "status": "SKIPPED_UNSUPPORTED_EXTENSION", "node_count": 0, "edge_count": 0}

    sha256 = compute_sha256(abs_path)
    try:
        stat = abs_path.stat()
        mtime = stat.st_mtime
        size_bytes = stat.st_size
    except OSError as exc:
        return {"file_path": canon, "status": "ERROR", "error": str(exc)}

    nodes, signatures, edges, hooks, parse_status, err_msg = parse_source_file(canon, display, str(abs_path))

    try:
        conn = get_connection(root, read_only=False, timeout_ms=5000)
        with conn:
            delete_file_records(conn, canon)
            record_file_parsed(
                conn, canon, display, sha256, mtime, size_bytes,
                parse_status, len(nodes), len(edges), err_msg
            )
            batch_insert_nodes(conn, nodes)
            batch_insert_signatures(conn, signatures)
            batch_insert_edges(conn, edges)
            batch_insert_lifecycle_hooks(conn, hooks)
        conn.close()
    except Exception as exc:
        return {"file_path": canon, "status": "DB_ERROR", "error": str(exc)}

    return {
        "file_path": canon,
        "status": parse_status,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "error": err_msg,
    }
