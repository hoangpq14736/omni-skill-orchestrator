"""Lifecycle Registration Guard for Omni-Graph (Graphify)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

class LifecycleRegistrationGuard:
    """
    Checks that lifecycle hooks (e.g. Discord slash commands, FastAPI endpoints)
    are registered/synchronized in the codebase.
    """

    @staticmethod
    def _collect_python_sources(root: Path) -> Dict[Path, str]:
        sources: Dict[Path, str] = {}
        for py_file in root.rglob("*.py"):
            try:
                sources[py_file] = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
        return sources

    @staticmethod
    def check_lifecycle_registrations(conn: sqlite3.Connection, workspace_root: Optional[Path | str] = None) -> List[Dict]:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
                hook_name,
                handler_node_id,
                file_path,
                line_number
            FROM lifecycle_hooks
            """
        )
        rows = cursor.fetchall()
        hooks = [
            {
                "hook_id": str(row[0]),
                "hook_name": str(row[1]),
                "handler_node_id": str(row[2]),
                "file_path": str(row[3]),
                "line_number": int(row[4]),
            }
            for row in rows
        ]

        root = Path(workspace_root).resolve() if workspace_root else Path.cwd().resolve()
        sources = LifecycleRegistrationGuard._collect_python_sources(root)

        tree_sync_pat = re.compile(r"\b(?:bot\.)?tree\.sync\s*\(")
        add_cog_pat = re.compile(r"\b(?:add_cog|load_extension)\s*\(")
        include_router_pat = re.compile(r"\binclude_router\s*\(")
        apirouter_def_pat = re.compile(r"\bAPIRouter\s*\(")

        diagnostics: List[Dict] = []

        any_tree_sync = any(tree_sync_pat.search(txt) for txt in sources.values())
        any_include_router = any(include_router_pat.search(txt) for txt in sources.values())

        for hook in hooks:
            rel_file = hook["file_path"]
            hook_name = hook["hook_name"]
            is_registered = True
            message = "Hook appears to be registered."
            suggested_fix: Optional[str] = None

            matched_file = None
            for p in sources:
                if p.as_posix().lower().endswith(rel_file.lower()):
                    matched_file = p
                    break

            if hook_name == "app_command":
                if not any_tree_sync:
                    is_registered = False
                    message = "Discord slash command handler defined, but no `bot.tree.sync()` found in workspace."
                    suggested_fix = "Call `await bot.tree.sync()` during bot startup/on_ready."
            elif hook_name == "fastapi_endpoint":
                if matched_file and apirouter_def_pat.search(sources[matched_file]):
                    if not any_include_router:
                        is_registered = False
                        message = "FastAPI endpoint defined on APIRouter that is never included via `include_router`."
                        suggested_fix = "Add `app.include_router(...)` in main app entrypoint."

            diagnostics.append({
                **hook,
                "is_registered": is_registered,
                "message": message,
                "suggested_fix": suggested_fix,
            })

        return diagnostics
