import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import hook_runner
from memory_utils import canonical_workspace_hash
from omni_graph.traversal import compute_blast_radius, query_file_callers
from omni_graph.validator import audit_callers_of_file, audit_js_ts_calls, audit_python_calls
from resolver import build_cognitive_pre_flight
from omni_graph.fingerprint import detect_dirty_files
from omni_graph.git_hygiene import ensure_git_hooks
from omni_graph.self_healing import micro_index_file
from omni_graph.storage import get_connection, init_db, record_file_parsed


def test_hooks_json_registers_post_tool_use():
    data = json.loads((_REPO_ROOT / "hooks.json").read_text(encoding="utf-8"))
    gk = data.get("omni-kernel-gatekeeper", data)
    post_hooks = [h for block in gk.get("PostToolUse", []) for h in block.get("hooks", [])]
    assert post_hooks, "Expected PostToolUse hooks in hooks.json"
    for h in post_hooks:
        cmd = h.get("command", "")
        assert "python -S" in cmd and "-B" in cmd and "scripts/hook_runner.py" in cmd
        assert h.get("timeout", 99) <= 5


def test_detect_dirty_files_polyglot_default(tmp_path):
    (tmp_path / "app.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    (tmp_path / "index.ts").write_text("export function run() { return 1; }\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Docs\n", encoding="utf-8")

    conn = init_db(tmp_path)
    try:
        for rel in ("app.py", "index.ts", "README.md"):
            p = tmp_path / rel
            st = p.stat()
            record_file_parsed(conn, rel.lower(), rel, "h", st.st_mtime, st.st_size, "SUCCESS", 1, 0)
        res = detect_dirty_files(conn, tmp_path)
        assert res["deleted"] == [], f"Polyglot files should not be marked deleted: {res['deleted']}"
    finally:
        conn.close()


def test_micro_index_file_fresh_and_read_only(tmp_path, monkeypatch):
    src = tmp_path / "app.py"
    src.write_text("def compute(x):\n    return x + 1\n", encoding="utf-8")

    monkeypatch.setenv("OMNI_READ_ONLY", "1")
    ro_res = micro_index_file(tmp_path, "app.py")
    assert ro_res["status"] == "SKIPPED_READ_ONLY"
    assert not (tmp_path / ".omni" / "codebase_graph.db").exists()

    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    res = micro_index_file(tmp_path, "app.py")
    assert res["status"] == "SUCCESS"
    assert res["node_count"] >= 1
    assert (tmp_path / ".omni" / "codebase_graph.db").is_file()
    assert ".omni/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")

    conn = get_connection(tmp_path, read_only=True)
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM nodes").fetchall()]
        assert "compute" in names
    finally:
        conn.close()


def test_ensure_git_hooks_idempotent_and_safe(tmp_path, monkeypatch):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    custom_post_commit = hooks_dir / "post-commit"
    custom_post_commit.write_text("#!/bin/sh\necho custom-hook\n", encoding="utf-8")

    monkeypatch.setenv("OMNI_READ_ONLY", "1")
    assert ensure_git_hooks(tmp_path) is False
    assert "OMNI-GRAPH-HOOK-START" not in custom_post_commit.read_text(encoding="utf-8")

    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    assert ensure_git_hooks(tmp_path) is True
    for name in ("post-commit", "post-merge", "post-checkout"):
        text = (hooks_dir / name).read_text(encoding="utf-8")
        assert "OMNI-GRAPH-HOOK-START" in text
        assert "--scan" in text
    assert "echo custom-hook" in custom_post_commit.read_text(encoding="utf-8")

    # Idempotent second run
    assert ensure_git_hooks(tmp_path) is False


def test_hook_runner_post_tool_use_and_preinvocation_sync(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    mod_file = tmp_path / "mod.py"
    mod_file.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    ws_hash = canonical_workspace_hash(str(tmp_path))
    marker = Path(hook_runner._SCRIPT_DIR) / f".omni_graph_scan.{ws_hash[:12]}.ts"
    lock_file = Path(str(marker) + ".lock")

    try:
        # 1. PostToolUse returns {} and micro-indexes edited file into real codebase_graph.db
        with patch("subprocess.Popen") as mock_popen:
            res = hook_runner.process_hook({
                "hookEventName": "PostToolUse",
                "workspacePaths": [str(tmp_path)],
                "toolCall": {"name": "edit_file", "args": {"Path": str(mod_file)}},
            })
            assert res == {}
            assert mock_popen.call_count == 1  # Cold-start background --scan since DB did not exist

        conn = get_connection(tmp_path, read_only=True)
        try:
            names = [r[0] for r in conn.execute("SELECT name FROM nodes").fetchall()]
            assert "greet" in names
        finally:
            conn.close()

        # 2. Debounce suppresses duplicate background scan within 60s
        git_dir = tmp_path / ".git"
        git_dir.mkdir(exist_ok=True)
        git_index = git_dir / "index"
        git_index.write_text("idx", encoding="utf-8")
        db_file = tmp_path / ".omni" / "codebase_graph.db"
        past = time.time() - 120
        os.utime(db_file, (past, past))
        os.utime(git_index, (past + 10, past + 10))

        with patch("subprocess.Popen") as mock_popen:
            hook_runner._maybe_sync_omni_graph(str(tmp_path))
            assert mock_popen.call_count == 0

        # 3. Expired debounce + newer .git/index triggers background --scan
        marker.write_text(str(time.time() - 61.0), encoding="utf-8")
        with patch("subprocess.Popen") as mock_popen:
            hook_runner._maybe_sync_omni_graph(str(tmp_path))
            assert mock_popen.call_count == 1
            argv = mock_popen.call_args[0][0]
            assert "--scan" in argv and str(tmp_path) in argv

        # 4. OMNI_READ_ONLY=1 prevents any write or spawn
        marker.unlink(missing_ok=True)
        monkeypatch.setenv("OMNI_READ_ONLY", "1")
        with patch("subprocess.Popen") as mock_popen:
            assert hook_runner.process_hook({
                "hookEventName": "PostToolUse",
                "workspacePaths": [str(tmp_path)],
                "toolCall": {"name": "edit_file", "args": {"Path": str(mod_file)}},
            }) == {}
            hook_runner._maybe_sync_omni_graph(str(tmp_path))
            assert mock_popen.call_count == 0
    finally:
        marker.unlink(missing_ok=True)
        lock_file.unlink(missing_ok=True)


def test_traversal_no_substring_collision_and_file_callers(tmp_path):
    svc = tmp_path / "svc.py"
    svc.write_text(
        "def run(item_id):\n    return item_id\n\n"
        "def prune_data(x):\n    return x\n",
        encoding="utf-8",
    )
    caller = tmp_path / "app.py"
    caller.write_text(
        "from svc import run\n\n"
        "def main():\n    return run(item_id=42)\n",
        encoding="utf-8",
    )
    unrelated = tmp_path / "other.py"
    unrelated.write_text(
        "from svc import prune_data\n\n"
        "def clean():\n    return prune_data(1)\n",
        encoding="utf-8",
    )
    micro_index_file(tmp_path, "svc.py")
    micro_index_file(tmp_path, "app.py")
    micro_index_file(tmp_path, "other.py")

    conn = get_connection(tmp_path, read_only=True)
    try:
        blast = compute_blast_radius(conn, "run")
        assert blast["impacted_files"] == ["app.py"]
        assert any(c["source_id"] == "app.py:main" for c in blast["direct_callers"])

        file_callers = query_file_callers(conn, "svc.py")
        syms = {item["symbol"]: item["callers"] for item in file_callers}
        assert "run" in syms and "prune_data" in syms
        assert syms["run"][0]["file_path"] == "app.py"
        assert syms["prune_data"][0]["file_path"] == "other.py"
    finally:
        conn.close()


def test_resolver_no_vietnamese_prose_false_match(tmp_path):
    doc_mod = tmp_path / "notes.py"
    doc_mod.write_text("def _markdown_paragraph_containing(txt):\n    return txt\n", encoding="utf-8")
    caller_mod = tmp_path / "runner.py"
    caller_mod.write_text("from notes import _markdown_paragraph_containing\n_markdown_paragraph_containing('x')\n", encoding="utf-8")
    micro_index_file(tmp_path, "notes.py")
    micro_index_file(tmp_path, "runner.py")

    pf_prose = build_cognitive_pre_flight("trong khi sua loi omni graph", str(tmp_path), [], [], [])
    assert not any("_markdown_paragraph_containing" in x for x in pf_prose["du_completeness"])

    pf_exact = build_cognitive_pre_flight("update notes.py handler", str(tmp_path), [], [], [])
    assert any("notes.py" in x and "_markdown_paragraph_containing" in x for x in pf_exact["du_completeness"])


def test_pretooluse_signature_guard_blocks_invalid_kwarg(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    core_dir = tmp_path / "core"
    cogs_dir = tmp_path / "cogs"
    core_dir.mkdir()
    cogs_dir.mkdir()
    (core_dir / "docker_manager.py").write_text(
        "def start_server(server_id: str, ram: str = '2G'):\n    return server_id, ram\n",
        encoding="utf-8",
    )
    cog_file = cogs_dir / "server_cog.py"
    cog_file.write_text("def cmd():\n    return 1\n", encoding="utf-8")

    micro_index_file(tmp_path, "core/docker_manager.py")
    micro_index_file(tmp_path, "cogs/server_cog.py")

    bad_edit = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement server command",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(cog_file),
                "Target": "    return 1",
                "Replacement": "    return start_server(server_id='s1', allocated_ram='4G')",
            },
        },
    })
    assert bad_edit["decision"] == "deny"
    assert "allocated_ram" in bad_edit["reason"]
    assert "ram" in bad_edit["reason"]

    good_edit = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement server command",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(cog_file),
                "Target": "    return 1",
                "Replacement": "    return start_server(server_id='s1', ram='4G')",
            },
        },
    })
    assert good_edit["decision"] == "allow"


def test_posttooluse_and_preinvocation_deliver_caller_and_drift_memory(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    dm = tmp_path / "docker_manager.py"
    dm.write_text("def launch_box(box_id: str, ram: str = '2G'):\n    return box_id\n", encoding="utf-8")
    cog = tmp_path / "server_cog.py"
    cog.write_text("def run_cmd():\n    return launch_box(box_id='1', ram='4G')\n", encoding="utf-8")
    micro_index_file(tmp_path, "docker_manager.py")
    micro_index_file(tmp_path, "server_cog.py")

    # Rename parameter ram -> memory_gb in docker_manager.py and run PostToolUse
    dm.write_text("def launch_box(box_id: str, memory_gb: str = '2G'):\n    return box_id\n", encoding="utf-8")
    ws_hash = canonical_workspace_hash(str(tmp_path))
    marker = Path(hook_runner._SCRIPT_DIR) / f".omni_graph_scan.{ws_hash[:12]}.ts"
    lock_file = Path(str(marker) + ".lock")
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"tool_calls": [{"name": "read_file", "args": {"Path": str(cog)}}]}) + "\n",
        encoding="utf-8",
    )
    try:
        assert hook_runner.process_hook({
            "hookEventName": "PostToolUse",
            "workspacePaths": [str(tmp_path)],
            "toolCall": {"name": "edit_file", "args": {"Path": str(dm)}},
        }) == {}

        # Also test direct PreInvocation delivery without relying on external skill registry
        adv = hook_runner._build_active_graph_advisory(str(tmp_path), str(transcript))
        assert "docker_manager.py" in adv
        assert "launch_box" in adv
        assert "server_cog.py:2" in adv
        assert "Contract Alert" in adv
        assert "UNEXPECTED_KEYWORD_ARG" in adv
    finally:
        marker.unlink(missing_ok=True)
        lock_file.unlink(missing_ok=True)


def test_python_import_disambiguation_across_duplicate_names(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    (tmp_path / "core").mkdir()
    (tmp_path / "net").mkdir()
    (tmp_path / "core" / "db.py").write_text("def connect(host: str, port: int = 5432):\n    return host\n", encoding="utf-8")
    (tmp_path / "net" / "http.py").write_text("def connect(url: str, timeout: int = 5):\n    return url\n", encoding="utf-8")
    app = tmp_path / "app.py"
    app.write_text("from core.db import connect\n\ndef init():\n    return 1\n", encoding="utf-8")

    micro_index_file(tmp_path, "core/db.py")
    micro_index_file(tmp_path, "net/http.py")
    micro_index_file(tmp_path, "app.py")

    bad = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement db connect",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(app),
                "Target": "    return 1",
                "Replacement": "    return connect(url='http://example.com')",
            },
        },
    })
    assert bad["decision"] == "deny"
    assert "UNEXPECTED_KEYWORD_ARG" in bad["reason"]

    good = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement db connect",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(app),
                "Target": "    return 1",
                "Replacement": "    return connect(host='localhost', port=5432)",
            },
        },
    })
    assert good["decision"] == "allow"


def test_js_ts_pretooluse_signature_guard_and_visitor(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    (tmp_path / "src").mkdir()
    api_ts = tmp_path / "src" / "api.ts"
    api_ts.write_text(
        "export function fetchUser(userId: string, includeMeta?: boolean): Promise<void> {\n"
        "  return Promise.resolve();\n"
        "}\n",
        encoding="utf-8",
    )
    page_ts = tmp_path / "src" / "page.ts"
    page_ts.write_text("import { fetchUser } from './api';\nconst x = 1;\n", encoding="utf-8")

    micro_index_file(tmp_path, "src/api.ts")
    micro_index_file(tmp_path, "src/page.ts")

    bad_missing = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement page fetch",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(page_ts),
                "Target": "const x = 1;",
                "Replacement": "fetchUser();",
            },
        },
    })
    assert bad_missing["decision"] == "deny"
    assert "MISSING_REQUIRED_ARG" in bad_missing["reason"]

    bad_extra = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement page fetch",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(page_ts),
                "Target": "const x = 1;",
                "Replacement": "fetchUser('u1', true, 'extra');",
            },
        },
    })
    assert bad_extra["decision"] == "deny"
    assert "TOO_MANY_POSITIONAL_ARGS" in bad_extra["reason"]

    good = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement page fetch",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(page_ts),
                "Target": "const x = 1;",
                "Replacement": "fetchUser('u1');",
            },
        },
    })
    assert good["decision"] == "allow"


def test_mcp_worker_post_and_pre_tool_use(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    svc = tmp_path / "svc.py"
    svc.write_text("def save_item(item_id: str, count: int = 1):\n    return item_id\n", encoding="utf-8")
    worker_target = tmp_path / "worker_out.py"
    worker_target.write_text("def run_worker():\n    return save_item(item_id='a')\n", encoding="utf-8")
    micro_index_file(tmp_path, "svc.py")

    # 1. Read-only MCP tool passes immediately
    ro_mcp = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "toolCall": {
            "name": "call_mcp_tool",
            "args": {"ServerName": "gemini-api", "ToolName": "gemini_search_docs", "Arguments": {"query": "test"}},
        },
    })
    assert ro_mcp == {"decision": "allow"}

    # 2. Mutating MCP with invalid inline source_code is caught by Signature Guard
    bad_mcp = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement worker call",
        "toolCall": {
            "name": "call_mcp_tool",
            "args": {
                "ServerName": "gemini_worker_cloud",
                "ToolName": "gemini_fast_edit",
                "Arguments": {
                    "file_path": str(worker_target),
                    "source_code": "def run_worker():\n    return save_item(id='a')\n",
                },
            },
        },
    })
    assert bad_mcp["decision"] == "deny"
    assert "UNEXPECTED_KEYWORD_ARG" in bad_mcp["reason"]

    # 3. PostToolUse on gemini_fast_edit immediately micro-indexes worker_out.py
    assert hook_runner.process_hook({
        "hookEventName": "PostToolUse",
        "workspacePaths": [str(tmp_path)],
        "toolCall": {
            "name": "call_mcp_tool",
            "args": {
                "ServerName": "gemini_worker_cloud",
                "ToolName": "gemini_fast_edit",
                "Arguments": {"file_path": str(worker_target), "instruction": "update"},
            },
        },
    }) == {}
    conn = get_connection(tmp_path, read_only=True)
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM nodes WHERE file_path = 'worker_out.py'").fetchall()]
        assert "run_worker" in names
    finally:
        conn.close()


def test_js_ts_class_methods_object_options_and_strings(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    (tmp_path / "src").mkdir()
    svc_ts = tmp_path / "src" / "docker.ts"
    svc_ts.write_text(
        "export class DockerService {\n"
        "  async startBox(boxId: string, ram?: string): Promise<void> {\n"
        "    return;\n"
        "  }\n"
        "}\n"
        "export default function bootServer({ serverId, ram = '2G' }: { serverId: string; ram?: string }) {\n"
        "  return { serverId, ram };\n"
        "}\n",
        encoding="utf-8",
    )
    app_ts = tmp_path / "src" / "app.ts"
    app_ts.write_text(
        "import bootServer, { DockerService } from './docker';\n"
        "const msg = 'bootServer({ bogus: 1 }) startBox()';\n",
        encoding="utf-8",
    )

    micro_index_file(tmp_path, "src/docker.ts")
    micro_index_file(tmp_path, "src/app.ts")

    # 1. String literal containing fake calls must NOT trigger violations
    conn = get_connection(tmp_path, read_only=True)
    try:
        assert audit_js_ts_calls(conn, app_ts.read_text(encoding="utf-8")) == []
    finally:
        conn.close()

    # 2. Class method missing required arg is caught
    bad_method = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement docker start",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(app_ts),
                "Target": "const msg = 'bootServer({ bogus: 1 }) startBox()';",
                "Replacement": "const s = new DockerService();\ns.startBox();",
            },
        },
    })
    assert bad_method["decision"] == "deny"
    assert "MISSING_REQUIRED_ARG" in bad_method["reason"]

    # 3. Destructured option object key typo is caught (allocatedRam vs ram)
    bad_opt = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement server boot",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(app_ts),
                "Target": "const msg = 'bootServer({ bogus: 1 }) startBox()';",
                "Replacement": "bootServer({ serverId: 's1', allocatedRam: '4G' });",
            },
        },
    })
    assert bad_opt["decision"] == "deny"
    assert "UNEXPECTED_KEYWORD_ARG" in bad_opt["reason"]
    assert "allocatedRam" in bad_opt["reason"]


def test_pretooluse_injects_caller_constraints_into_instruction_mcp(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    core_py = tmp_path / "core.py"
    core_py.write_text("def process_order(order_id: str):\n    return order_id\n", encoding="utf-8")
    caller_py = tmp_path / "routes.py"
    caller_py.write_text("from core import process_order\nprocess_order('o1')\n", encoding="utf-8")
    micro_index_file(tmp_path, "core.py")
    micro_index_file(tmp_path, "routes.py")

    res = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement order update",
        "toolCall": {
            "name": "call_mcp_tool",
            "args": {
                "ServerName": "gemini_worker_cloud",
                "ToolName": "gemini_fast_edit",
                "Arguments": {
                    "file_path": str(core_py),
                    "instruction": "Add logging to process_order",
                },
            },
        },
    })
    assert res["decision"] == "allow"
    assert "overwrite" in res
    injected_inst = res["overwrite"]["Arguments"]["instruction"]
    assert "[Omni-Graph Constraints]" in injected_inst
    assert "process_order" in injected_inst
    assert "routes.py" in injected_inst


def test_ts_cross_file_interface_and_type_alias_validation(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "types.ts").write_text(
        "export interface ServerConfig {\n"
        "  serverId: string;\n"
        "  ram?: string;\n"
        "}\n"
        "export type BootOpts = {\n"
        "  image: string;\n"
        "  dryRun?: boolean;\n"
        "};\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "docker.ts").write_text(
        "import { ServerConfig, BootOpts } from './types';\n"
        "export function startConfigured(opts: ServerConfig) {\n"
        "  return opts;\n"
        "}\n"
        "export function bootImage(opts: BootOpts) {\n"
        "  return opts;\n"
        "}\n",
        encoding="utf-8",
    )
    app_ts = tmp_path / "src" / "main.ts"
    app_ts.write_text("import { startConfigured, bootImage } from './docker';\nconst k = 1;\n", encoding="utf-8")

    micro_index_file(tmp_path, "src/types.ts")
    micro_index_file(tmp_path, "src/docker.ts")
    micro_index_file(tmp_path, "src/main.ts")

    # 1. Wrong option key against cross-file interface ServerConfig
    bad_key = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement docker start",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(app_ts),
                "Target": "const k = 1;",
                "Replacement": "startConfigured({ serverId: 's1', allocatedRam: '4G' });",
            },
        },
    })
    assert bad_key["decision"] == "deny"
    assert "UNEXPECTED_KEYWORD_ARG" in bad_key["reason"]
    assert "allocatedRam" in bad_key["reason"]

    # 2. Missing required key against cross-file type alias BootOpts
    missing_req = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement boot image",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(app_ts),
                "Target": "const k = 1;",
                "Replacement": "bootImage({ dryRun: true });",
            },
        },
    })
    assert missing_req["decision"] == "deny"
    assert "MISSING_REQUIRED_KWONLY_ARG" in missing_req["reason"]
    assert "image" in missing_req["reason"]

    # 3. Valid call passes
    good = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement docker start",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(app_ts),
                "Target": "const k = 1;",
                "Replacement": "startConfigured({ serverId: 's1', ram: '4G' });\nbootImage({ image: 'node:20' });",
            },
        },
    })
    assert good["decision"] == "allow"


def test_ts_extends_pick_omit_and_intersection(tmp_path, monkeypatch):
    monkeypatch.delenv("OMNI_READ_ONLY", raising=False)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "models.ts").write_text(
        "export interface BaseEntity {\n"
        "  id: string;\n"
        "  name: string;\n"
        "  tag?: string;\n"
        "}\n"
        "export interface ExtendedCfg extends BaseEntity {\n"
        "  region: string;\n"
        "}\n"
        "export type PickedCfg = Pick<BaseEntity, 'id' | 'tag'>;\n"
        "export type OmittedCfg = Omit<BaseEntity, 'id'>;\n"
        "export type InterCfg = BaseEntity & { extra: number };\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "svc.ts").write_text(
        "import { ExtendedCfg, PickedCfg, OmittedCfg, InterCfg } from './models';\n"
        "export function fnExt(o: ExtendedCfg) { return o; }\n"
        "export function fnPick(o: PickedCfg) { return o; }\n"
        "export function fnOmit(o: OmittedCfg) { return o; }\n"
        "export function fnInter(o: InterCfg) { return o; }\n",
        encoding="utf-8",
    )
    app_ts = tmp_path / "src" / "use.ts"
    app_ts.write_text("import { fnExt, fnPick, fnOmit, fnInter } from './svc';\nconst z = 0;\n", encoding="utf-8")

    micro_index_file(tmp_path, "src/models.ts")
    micro_index_file(tmp_path, "src/svc.ts")
    micro_index_file(tmp_path, "src/use.ts")

    # 1. extends: missing parent required field `id`
    r1 = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement ext",
        "toolCall": {"name": "edit_file", "args": {"Path": str(app_ts), "Target": "const z = 0;", "Replacement": "fnExt({ name: 'a', region: 'us' });"}},
    })
    assert r1["decision"] == "deny" and "MISSING_REQUIRED_KWONLY_ARG" in r1["reason"] and "id" in r1["reason"]

    # 2. Pick: passing omitted field `name` triggers UNEXPECTED_KEYWORD_ARG
    r2 = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement pick",
        "toolCall": {"name": "edit_file", "args": {"Path": str(app_ts), "Target": "const z = 0;", "Replacement": "fnPick({ id: '1', name: 'bad' });"}},
    })
    assert r2["decision"] == "deny" and "UNEXPECTED_KEYWORD_ARG" in r2["reason"] and "name" in r2["reason"]

    # 3. Omit: passing omitted field `id` triggers UNEXPECTED_KEYWORD_ARG
    r3 = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement omit",
        "toolCall": {"name": "edit_file", "args": {"Path": str(app_ts), "Target": "const z = 0;", "Replacement": "fnOmit({ id: '1', name: 'ok' });"}},
    })
    assert r3["decision"] == "deny" and "UNEXPECTED_KEYWORD_ARG" in r3["reason"] and "id" in r3["reason"]

    # 4. Intersection &: missing `& { extra }` field `extra` caught; valid call allowed
    r4 = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement inter",
        "toolCall": {"name": "edit_file", "args": {"Path": str(app_ts), "Target": "const z = 0;", "Replacement": "fnInter({ id: '1', name: 'ok' });"}},
    })
    assert r4["decision"] == "deny" and "MISSING_REQUIRED_KWONLY_ARG" in r4["reason"] and "extra" in r4["reason"]

    ok = hook_runner.process_hook({
        "hookEventName": "PreToolUse",
        "workspacePaths": [str(tmp_path)],
        "lastUserInput": "implement valid",
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": str(app_ts),
                "Target": "const z = 0;",
                "Replacement": (
                    "fnExt({ id: '1', name: 'a', region: 'us' });\n"
                    "fnPick({ id: '1' });\n"
                    "fnOmit({ name: 'a' });\n"
                    "fnInter({ id: '1', name: 'a', extra: 5 });"
                ),
            },
        },
    })
    assert ok["decision"] == "allow"
