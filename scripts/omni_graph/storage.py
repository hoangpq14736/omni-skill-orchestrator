"""SQLite WAL Relational Storage Engine for Omni-Graph (Graphify)."""

import os
import time
import json
from pathlib import Path
import sqlite3

def get_db_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / '.omni' / 'codebase_graph.db'

def get_connection(workspace_root: str | Path, read_only: bool = False, timeout_ms: int = 5000) -> sqlite3.Connection:
    db_path = get_db_path(workspace_root)
    if not read_only:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    if read_only:
        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")
        uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    else:
        uri = f"file:{db_path.resolve().as_posix()}"
    conn = sqlite3.connect(uri, uri=True, timeout=timeout_ms / 1000.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn_or_workspace) -> sqlite3.Connection:
    if isinstance(conn_or_workspace, (str, Path)):
        conn = get_connection(conn_or_workspace)
    else:
        conn = conn_or_workspace

    with conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA temp_store = MEMORY")

        conn.execute("""
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
            )
        """)

        conn.execute("""
            CREATE VIEW IF NOT EXISTS file_hashes AS
            SELECT file_path, sha256 FROM codebase_files_meta
        """)

        conn.execute("""
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
            )
        """)

        conn.execute("""
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
                return_annotation   TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                source_id           TEXT NOT NULL,
                target_id           TEXT NOT NULL,
                relation_type       TEXT NOT NULL,
                file_path           TEXT NOT NULL REFERENCES codebase_files_meta(file_path) ON DELETE CASCADE,
                line_number         INTEGER NOT NULL,
                col_offset          INTEGER NOT NULL DEFAULT 0,
                call_args_count     INTEGER,
                call_kwargs         TEXT,
                has_splat_pos       BOOLEAN DEFAULT 0,
                has_splat_kw        BOOLEAN DEFAULT 0,
                is_awaited          BOOLEAN DEFAULT 0,
                PRIMARY KEY (source_id, target_id, relation_type, line_number, col_offset)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS lifecycle_hooks (
                id                  TEXT PRIMARY KEY,
                hook_name           TEXT NOT NULL,
                handler_node_id     TEXT REFERENCES nodes(id) ON DELETE CASCADE,
                file_path           TEXT NOT NULL,
                line_number         INTEGER NOT NULL,
                registration_style  TEXT NOT NULL,
                priority            INTEGER DEFAULT 100,
                is_registered       BOOLEAN NOT NULL DEFAULT 1
            )
        """)

        # Covering B-tree indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_tgt_rel ON edges(target_id, relation_type, source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_src_rel ON edges(source_id, relation_type, target_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_file ON edges(file_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name, node_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signatures_file ON signatures(file_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lifecycle_name ON lifecycle_hooks(hook_name, is_registered)")

    return conn

def delete_file_records(conn: sqlite3.Connection, canonical_file_path: str):
    with conn:
        conn.execute("DELETE FROM edges WHERE file_path = ?", (canonical_file_path,))
        conn.execute("DELETE FROM signatures WHERE file_path = ?", (canonical_file_path,))
        conn.execute("DELETE FROM nodes WHERE file_path = ?", (canonical_file_path,))
        conn.execute("DELETE FROM codebase_files_meta WHERE file_path = ?", (canonical_file_path,))

def clean_orphan_edges(conn: sqlite3.Connection):
    with conn:
        conn.execute("DELETE FROM edges WHERE source_id NOT IN (SELECT id FROM nodes)")

def record_file_parsed(conn: sqlite3.Connection, file_path: str, display_path: str, sha256: str,
                       mtime: float, size_bytes: int, parse_status: str, node_count: int,
                       edge_count: int, error_msg: str | None = None):
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO codebase_files_meta (
                file_path, display_path, sha256, mtime, size_bytes, parsed_at,
                parse_status, node_count, edge_count, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (file_path, display_path, sha256, mtime, size_bytes, time.time(), parse_status, node_count, edge_count, error_msg))

def batch_insert_nodes(conn: sqlite3.Connection, nodes_list: list[tuple]):
    if not nodes_list:
        return
    with conn:
        conn.executemany("""
            INSERT OR REPLACE INTO nodes (
                id, name, qualified_name, file_path, display_path,
                line_number, end_line_number, node_type, docstring, is_exported
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, nodes_list)

def batch_insert_signatures(conn: sqlite3.Connection, signatures_list: list[tuple]):
    if not signatures_list:
        return
    with conn:
        conn.executemany("""
            INSERT OR REPLACE INTO signatures (
                node_id, file_path, posonly_args, args, defaults_count,
                vararg, kwonly_args, kw_defaults, kwarg, return_annotation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, signatures_list)

def batch_insert_edges(conn: sqlite3.Connection, edges_list: list[tuple]):
    if not edges_list:
        return
    with conn:
        conn.executemany("""
            INSERT OR REPLACE INTO edges (
                source_id, target_id, relation_type, file_path, line_number,
                col_offset, call_args_count, call_kwargs, has_splat_pos, has_splat_kw, is_awaited
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, edges_list)

def batch_insert_lifecycle_hooks(conn: sqlite3.Connection, hooks_list: list[tuple]):
    if not hooks_list:
        return
    with conn:
        conn.executemany("""
            INSERT OR REPLACE INTO lifecycle_hooks (
                id, hook_name, handler_node_id, file_path, line_number,
                registration_style, priority, is_registered
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, hooks_list)
