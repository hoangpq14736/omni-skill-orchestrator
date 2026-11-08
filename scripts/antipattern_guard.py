"""
Omni-Kernel v4.1: Post-Execution Anti-Pattern Guard
Autonomously intercepts CLI failures, filters transient typos, and persists
structural, syntactic, and environment mismatch antipatterns into SQLite WAL.
Zero external dependencies, 100% Python Standard Library.
"""

import os
import re
import sys
import sqlite3
from typing import Optional, Dict, Any, Tuple

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_engine import record_antipattern, recall_antipatterns

# ----------------------------------------------------------------------------
# 1. Classification Patterns
# ----------------------------------------------------------------------------

# Errors that are transient or trivial user typos: DO NOT RECORD
_TRANSIENT_IGNORE_PATTERNS = [
    r"No such file",
    r"cannot find the path",
    r"FileNotFoundError",
    r"database is locked",
    r"Connection (?:refused|timed out|reset)",
    r"WinError\s+3[2-3]",
    r"KeyboardInterrupt",
    r"Cancelled",
    r"^\s*Usage:\s",
    r"^\s*Try ['\"-]?[a-zA-Z0-9_\-]+['\"]? for help",
    r"Target file .*? is outside approved workspaces",
]

# Structural, syntactic, tool-mismatch errors: ELIGIBLE FOR RECORDING
_ELIGIBLE_STRUCTURAL_PATTERNS = [
    # PowerShell cmdlet parsing errors
    (
        r"The term '.*?' is not recognized as the name of a cmdlet",
        "PowerShell regex quoting failure (unescaped .*? parsed as command)",
        "Wrap regex patterns in single quotes or write script to scratch directory"
    ),
    (
        r"The 'from' keyword is not supported in this version",
        "PowerShell multi-line Python -c parser rejection",
        "Avoid multi-line string with 'from' in PowerShell python -c; use temp script"
    ),
    (
        r"Missing argument in parameter list",
        "PowerShell parameter quoting / escaping syntax error",
        "Verify quote matching and escape nested quotes via backtick or scratch script"
    ),
    # Python command line syntax & string errors
    (
        r"unterminated string literal",
        "Unescaped quotes in inline Python command line",
        "Use triple-quotes or external python script file in scratch/"
    ),
    (
        r"SyntaxError: .*?",
        "Python inline code syntax violation",
        "Validate syntax or run through temporary script file"
    ),
    # SQLite schema mismatches
    (
        r"no such table:\s*([a-zA-Z0-9_]+)",
        "SQLite schema mismatch: queried non-existent table",
        "Verify active schema version or execute init_database() migration"
    ),
    (
        r"no such column:\s*([a-zA-Z0-9_]+)",
        "SQLite schema mismatch: queried non-existent column",
        "Check column name in memory_schema.py or run schema migration"
    ),
    # Python import resolution
    (
        r"ModuleNotFoundError:\s*No module named '([a-zA-Z0-9_]+)'",
        "Module import path missing scripts/ or root directory",
        "Ensure sys.path.insert(0, ...) is configured for local module directory"
    ),
    # Network & port collisions
    (
        r"(?:port is already allocated|address already in use|only one usage of each socket address)",
        "Network port collision / conflict",
        "Release existing listener or configure fallback alternate port"
    ),
]

_IGNORE_COMPILED = [re.compile(p, re.IGNORECASE) for p in _TRANSIENT_IGNORE_PATTERNS]
_ELIGIBLE_COMPILED = [
    (re.compile(pat, re.IGNORECASE), cause, guidance)
    for pat, cause, guidance in _ELIGIBLE_STRUCTURAL_PATTERNS
]


def _extract_command_pattern(command: str) -> str:
    """Extract a representative normalized pattern from the command."""
    if not command:
        return "unknown_command"
    cmd = command.strip()
    # Normalize excessive spaces
    cmd = re.sub(r"\s+", " ", cmd)
    # Truncate overly long inline commands for clean pattern matching
    if len(cmd) > 120:
        return cmd[:120]
    return cmd


def classify_cli_error(
    tool_name: str,
    command: str,
    exit_code: int,
    output_text: str
) -> Optional[Dict[str, str]]:
    """
    Classify a CLI execution error.
    Returns None for transient/ignored cases (typos, file not found, lock busy).
    Returns structured antipattern metadata for actionable structural failures.
    """
    if exit_code == 0:
        return None

    txt = (output_text or "").strip()
    if not txt:
        return None

    # Step 1: Check transient ignore patterns
    for ign_re in _IGNORE_COMPILED:
        if ign_re.search(txt):
            return None

    # Step 2: Check eligible structural patterns
    for elig_re, root_cause, mitigation in _ELIGIBLE_COMPILED:
        m = elig_re.search(txt)
        if m:
            return {
                "command_pattern": _extract_command_pattern(command),
                "error_signature": m.group(0),
                "root_cause": root_cause,
                "mitigation_guidance": mitigation,
            }

    # Unknown or unclassified failure -> skip to prevent bloat (Zero-Trust Heuristic)
    return None


def handle_post_execution(
    workspace_dir: str,
    tool_name: str,
    command_line: str,
    exit_code: int,
    output_text: str,
    conn_or_db: Optional[Any] = None
) -> Optional[Dict[str, Any]]:
    """
    Hook executed automatically post-execution when tool/command finishes.
    Safely captures structural failures, enforces deduplication, and records
    or increments trigger counts in episodic_antipatterns table.
    """
    if exit_code == 0:
        return None

    classified = classify_cli_error(tool_name, command_line, exit_code, output_text)
    if not classified:
        return None

    target_db = conn_or_db if conn_or_db is not None else "omni_memory.db"

    try:
        # Check if identical pattern already exists in workspace (Deduplication Guard)
        existing = recall_antipatterns(
            conn_or_db=target_db,
            workspace_dir=workspace_dir,
            tool_name=tool_name,
            command_text=classified["command_pattern"]
        )
        if existing:
            # Already exists and trigger_count was incremented by recall_antipatterns!
            return existing[0]

        # New distinct antipattern -> Record in SQLite WAL
        ap_id = record_antipattern(
            conn_or_db=target_db,
            workspace_dir=workspace_dir,
            tool_name=tool_name,
            command_pattern=classified["command_pattern"],
            error_signature=classified["error_signature"],
            root_cause=classified["root_cause"],
            mitigation_guidance=classified["mitigation_guidance"],
            ttl_days=14.0
        )
        classified["antipattern_id"] = ap_id
        return classified
    except Exception as e:
        sys.stderr.write(f"[!] Warning [AntipatternGuard] Failed to record antipattern: {e}\n")
        return None
