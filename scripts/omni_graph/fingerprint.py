"""Fast workspace fingerprinting and two-tier change detection for Omni-Graph."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Any
import sqlite3

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".omni",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".idea",
    ".vscode",
    "build",
    "dist",
    ".pytest_cache",
}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MiB
_READ_CHUNK = 64 * 1024  # 64 KiB

def compute_sha256(file_path: Path | str) -> str:
    path = Path(file_path)
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(_READ_CHUNK):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""

def _relative_to_root(root: Path, target: Path) -> Path:
    try:
        return target.relative_to(root)
    except ValueError:
        return target.resolve()

def normalize_canonical_path(
    workspace_root: Path | str, full_or_rel_path: Path | str
) -> Tuple[str, str]:
    root = Path(workspace_root).resolve()
    path = Path(full_or_rel_path)
    rel = _relative_to_root(root, path.resolve())
    display = rel.as_posix()
    canonical = display.lower()
    return canonical, display

DEFAULT_SUPPORTED_EXTENSIONS = (
    ".py", ".pyw", ".js", ".jsx", ".ts", ".tsx",
    ".mjs", ".cjs", ".go", ".rs", ".sql", ".sh",
    ".bash", ".ps1", ".md", ".json", ".yaml", ".yml"
)

def scan_workspace_files(
    workspace_root: Path | str, extensions: Iterable[str] = DEFAULT_SUPPORTED_EXTENSIONS
) -> List[Dict[str, Any]]:
    root = Path(workspace_root).resolve()
    extensions_set = {ext.lower() for ext in extensions}
    results: List[Dict[str, Any]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in DEFAULT_EXCLUDE_DIRS
        ]

        for fname in filenames:
            if Path(fname).suffix.lower() not in extensions_set:
                continue

            abs_path = Path(dirpath, fname)
            try:
                stat = abs_path.stat()
            except OSError:
                continue

            if stat.st_size > MAX_FILE_SIZE:
                continue

            canonical, display = normalize_canonical_path(root, abs_path)

            results.append(
                {
                    "canonical_path": canonical,
                    "display_path": display,
                    "abs_path": str(abs_path),
                    "mtime": stat.st_mtime,
                    "size_bytes": stat.st_size,
                }
            )
    return results

def detect_dirty_files(
    conn: sqlite3.Connection,
    workspace_root: Path | str,
    extensions: Iterable[str] = (".py",),
) -> Dict[str, Any]:
    root = Path(workspace_root).resolve()

    cur = conn.cursor()
    cur.execute(
        "SELECT file_path, mtime, size_bytes, sha256 FROM codebase_files_meta"
    )
    db_records = {
        row[0]: {"mtime": row[1], "size_bytes": row[2], "sha256": row[3]}
        for row in cur.fetchall()
    }
    cur.close()

    scanned = scan_workspace_files(root, extensions)

    dirty: List[Dict[str, Any]] = []
    unchanged = 0
    seen_in_fs = set()

    for entry in scanned:
        canon = entry["canonical_path"]
        seen_in_fs.add(canon)

        db_entry = db_records.get(canon)

        if db_entry is None:
            entry["sha256"] = compute_sha256(entry["abs_path"])
            dirty.append(entry)
            continue

        if (
            abs(db_entry["mtime"] - entry["mtime"]) < 1e-4
            and db_entry["size_bytes"] == entry["size_bytes"]
        ):
            unchanged += 1
            continue

        new_hash = compute_sha256(entry["abs_path"])
        if new_hash != db_entry["sha256"]:
            entry["sha256"] = new_hash
            dirty.append(entry)
        else:
            unchanged += 1

    deleted = [path for path in db_records if path not in seen_in_fs]

    return {
        "dirty": dirty,
        "deleted": deleted,
        "unchanged": unchanged,
        "total_scanned": len(scanned),
    }

__all__ = [
    "DEFAULT_EXCLUDE_DIRS",
    "MAX_FILE_SIZE",
    "compute_sha256",
    "normalize_canonical_path",
    "scan_workspace_files",
    "detect_dirty_files",
]
