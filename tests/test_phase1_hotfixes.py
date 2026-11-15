import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import sqlite3
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from memory_utils import canonical_workspace_hash
import memory_schema
import memory_engine
import hook_runner


def get_repo_root() -> Path:
    return _REPO_ROOT


def test_spec1_hooks_json():
    """Test 1: Verify hooks.json PreInvocation and PreToolUse use 'python -S scripts/hook_runner.py' with timeout <= 5."""
    hooks_json_path = get_repo_root() / "hooks.json"
    assert hooks_json_path.exists(), f"hooks.json not found at {hooks_json_path}"
    data = json.loads(hooks_json_path.read_text(encoding="utf-8"))

    gk = data.get("omni-kernel-gatekeeper", data)
    pre_inv = gk.get("PreInvocation", [])
    assert pre_inv, "Expected non-empty PreInvocation list in hooks.json"
    for entry in pre_inv:
        cmd = entry.get("command", "")
        assert "python -S" in cmd and "-B" in cmd and "scripts/hook_runner.py" in cmd, f"Unexpected PreInvocation cmd: {cmd!r}"
        assert entry.get("timeout", 99) <= 5, f"PreInvocation timeout exceeds 5s: {entry}"

    pre_tool_hooks = [h for block in gk.get("PreToolUse", []) for h in block.get("hooks", [])]
    assert pre_tool_hooks, "Expected non-empty PreToolUse hooks list in hooks.json"
    for h in pre_tool_hooks:
        cmd = h.get("command", "")
        assert "python -S" in cmd and "-B" in cmd and "scripts/hook_runner.py" in cmd, f"Unexpected PreToolUse cmd: {cmd!r}"
        assert h.get("timeout", 99) <= 5, f"PreToolUse timeout exceeds 5s: {h}"


def test_spec1_python_s_subprocess_smoke(tmp_path, capsys):
    """Test 2: Verify python -S hook_runner.py smoke and clean-checkout OMNI_READ_ONLY=1 indexer safety."""
    repo_root = get_repo_root()
    script_path = repo_root / "scripts" / "hook_runner.py"
    assert script_path.exists(), f"hook_runner.py not found at {script_path}"

    env = os.environ.copy()
    env["OMNI_READ_ONLY"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    payload = {
        "lastUserInput": "Implement Spec 1 hotfix",
        "workspacePaths": [str(repo_root)],
    }

    result = subprocess.run(
        [sys.executable, "-S", str(script_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        cwd=str(repo_root),
    )
    assert result.returncode == 0, f"Subprocess failed with stderr: {result.stderr}"
    output_data = json.loads(result.stdout.strip())
    assert isinstance(output_data, dict)
    assert "injectSteps" in output_data

    import indexer
    missing_reg = tmp_path / "clean_checkout" / "registry.json"
    existing_dir = tmp_path / "existing_checkout"
    existing_dir.mkdir(exist_ok=True)
    existing_reg = existing_dir / "registry.json"
    sentinel_bytes = b'{"sentinel": true}\n'
    existing_reg.write_bytes(sentinel_bytes)

    from omni_graph import storage as graph_storage
    graph_ws = tmp_path / "graph_ro_ws"
    graph_ws.mkdir(exist_ok=True)
    gconn = graph_storage.init_db(graph_ws)
    gconn.close()
    for suffix in ("-shm", "-wal"):
        (graph_ws / ".omni" / f"codebase_graph.db{suffix}").unlink(missing_ok=True)

    ro_mem_db = tmp_path / "ro_wal_mem.db"
    mconn = memory_schema.init_database(str(ro_mem_db))
    mconn.close()
    for suffix in ("-shm", "-wal"):
        Path(f"{ro_mem_db}{suffix}").unlink(missing_ok=True)

    with patch.dict(os.environ, {"OMNI_READ_ONLY": "1"}):
        reg = indexer.build_index(str(missing_reg))
        indexer.build_index(str(existing_reg))
        ro_gconn = graph_storage.get_connection(graph_ws, read_only=True, timeout_ms=50)
        ro_gconn.execute("SELECT COUNT(*) FROM nodes").fetchone()
        ro_gconn.close()
        memory_engine.recall_episodic_memory("wal test", workspace_dir=str(graph_ws), top_k=3, db_path=str(ro_mem_db))

    assert not missing_reg.exists(), "indexer.build_index must not write registry.json when OMNI_READ_ONLY=1"
    assert existing_reg.read_bytes() == sentinel_bytes, "indexer.build_index must preserve existing registry.json under OMNI_READ_ONLY=1"
    assert not (graph_ws / ".omni" / "codebase_graph.db-shm").exists()
    assert not (graph_ws / ".omni" / "codebase_graph.db-wal").exists()
    assert not Path(f"{ro_mem_db}-shm").exists()
    assert not Path(f"{ro_mem_db}-wal").exists()
    assert isinstance(reg, dict) and "skills" in reg
    captured = capsys.readouterr()
    assert captured.out == "", f"indexer.build_index polluted stdout: {captured.out!r}"


def test_spec1_consolidator_60s_debounce(tmp_path):
    """Test 3: Verify 60s per-workspace debounce on consolidator spawn and OMNI_READ_ONLY=1 skip."""
    spool_file = tmp_path / "l1_staging_spool.jsonl"
    spool_file.write_text('{"session_id": "test"}\n' * 1600, encoding="utf-8")  # > 25 KB
    ws_hash = canonical_workspace_hash(str(tmp_path))
    ts_file = tmp_path / f".consolidator_spawn.{ws_hash[:12]}.ts"
    ws_other = tmp_path / "other_ws"
    ws_other.mkdir(exist_ok=True)
    ts_other = tmp_path / f".consolidator_spawn.{canonical_workspace_hash(str(ws_other))[:12]}.ts"
    last_act = tmp_path / "last_activation.json"
    act_hist = tmp_path / "activations_history.jsonl"

    mock_resolution = {
        "skills": [{
            "skill": {"name": "spec-driven-development", "version": "4.3.0", "source_type": "PLUGIN"},
            "raw_score": 95.0,
            "arbitration_reason": "test",
        }],
        "inferred_rules": ["Kernel Ring 0 Security"],
        "suggested_mcp": [],
        "cognitive_pre_flight": {},
        "tier_assessment": {"tier": 1, "tier_name": "L1 Reflex"},
        "proven_traces": [],
    }
    payload = {
        "lastUserInput": "implement spec 1 hotfix debounce",
        "workspacePaths": [str(tmp_path)],
    }

    with patch.object(hook_runner, "_SCRIPT_DIR", str(tmp_path)), \
         patch.object(hook_runner, "LAST_ACTIVATION_PATH", str(last_act)), \
         patch.object(hook_runner, "ACTIVATIONS_HISTORY_PATH", str(act_hist)), \
         patch("resolver.resolve_skill", return_value=mock_resolution), \
         patch("subprocess.Popen") as mock_popen, \
         patch.dict(os.environ, {"OMNI_READ_ONLY": ""}, clear=False):
        os.environ.pop("OMNI_READ_ONLY", None)

        # 1. First call >25KB spawns consolidator.py WITHOUT -S and writes .consolidator_spawn.ts
        hook_runner.process_hook(payload)
        assert mock_popen.call_count == 1
        spawn_argv = mock_popen.call_args[0][0]
        assert "-S" not in spawn_argv, f"Consolidator must NOT spawn with -S: {spawn_argv}"
        assert any("consolidator.py" in str(a) for a in spawn_argv)
        assert ts_file.exists()

        # 2. Immediate second call AND boundary <60s (59s) suppress duplicate spawn
        hook_runner.process_hook(payload)
        assert mock_popen.call_count == 1
        ts_file.write_text(str(time.time() - 59.0), encoding="utf-8")
        hook_runner.process_hook(payload)
        assert mock_popen.call_count == 1

        # 3. After >=60s elapsed (61s), third call spawns consolidator.py again
        ts_file.write_text(str(time.time() - 61.0), encoding="utf-8")
        hook_runner.process_hook(payload)
        assert mock_popen.call_count == 2

        # 3b. Distinct workspace is NOT debounced by tmp_path's marker
        hook_runner.process_hook({
            "lastUserInput": "implement spec 1 hotfix debounce",
            "workspacePaths": [str(ws_other)],
        })
        assert mock_popen.call_count == 3
        assert ts_other.exists()

        # 4. OMNI_READ_ONLY=1 prevents spool append, Popen, and telemetry writes
        size_before_ro = spool_file.stat().st_size
        hist_size_before_ro = act_hist.stat().st_size if act_hist.exists() else 0
        last_act_content_before_ro = last_act.read_text(encoding="utf-8") if last_act.exists() else None
        last_act.unlink(missing_ok=True)
        with patch.dict(os.environ, {"OMNI_READ_ONLY": "1"}):
            hook_runner.process_hook(payload)
            assert mock_popen.call_count == 3
            assert spool_file.stat().st_size == size_before_ro
            assert not last_act.exists(), "LAST_ACTIVATION_PATH must not be written when OMNI_READ_ONLY=1"
            assert (act_hist.stat().st_size if act_hist.exists() else 0) == hist_size_before_ro
            res_pre = hook_runner.process_hook({
                "hookEventName": "PreToolUse",
                "toolCall": {"name": "write_file", "args": {"Path": str(tmp_path / "docs" / "probe.md")}},
                "workspacePaths": [str(tmp_path)],
                "lastUserInput": "write a doc",
            })
            assert res_pre == {"decision": "allow"}
            assert not (tmp_path / ".omni" / "plan_unlocked.json").exists(), "PreToolUse must not write unlock marker when OMNI_READ_ONLY=1"
        if last_act_content_before_ro is not None:
            last_act.write_text(last_act_content_before_ro, encoding="utf-8")


def test_spec2_pure_fts5_bm25_fallback(tmp_path):
    """Test 4: Initialize a temp SQLite DB using memory_schema.init_database(db_path), insert an Active row into workspace_episodic_memory (matching canonical_workspace_hash(ws_dir)) with 0 rows in dense_embeddings, block/raise in sys.modules['embedding_service'] if imported, and verify memory_engine.recall_episodic_memory('sqlite wal deadlock', workspace_dir=ws_dir, top_k=3, db_path=db_path) returns the matching record via pure FTS5 BM25 without touching embedding_service."""

    db_path = str(tmp_path / "test_memory.db")
    ws_dir = str(tmp_path / "test_workspace")
    Path(ws_dir).mkdir(exist_ok=True)

    # Initialize database
    conn = memory_schema.init_database(db_path)
    conn.close()

    ws_hash = canonical_workspace_hash(ws_dir)

    # Insert test record into workspace_episodic_memory
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure columns match memory_schema: memory_id, workspace_hash, workspace_path, memory_type, title, problem_signature, solution_payload, context_metadata, bilingual_tags, content_folded, status, last_accessed_at, created_at
    cursor.execute("""
        INSERT INTO workspace_episodic_memory (
            memory_id, workspace_hash, workspace_path, memory_type, title,
            problem_signature, solution_payload, context_metadata, bilingual_tags,
            content_folded, status, last_accessed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "mem-001",
        ws_hash,
        ws_dir,
        "bugfix",
        "SQLite WAL deadlock issue",
        "sqlite wal deadlock",
        "Apply PRAGMA journal_mode=WAL; handle busy timeout.",
        "{}",
        "sqlite, deadlock, wal",
        "sqlite wal deadlock resolution payload",
        "Active",
        time.time(),
        time.time()
    ))
    conn.commit()
    conn.close()

    # Block/raise in sys.modules['embedding_service'] and assert zero calls
    embedding_calls = []

    class DummyEmbeddingServiceModule:
        def __getattr__(self, name):
            embedding_calls.append(name)
            raise RuntimeError("embedding_service should not be imported or used in pure FTS5 BM25 fallback mode!")

    with patch.dict(sys.modules, {"embedding_service": DummyEmbeddingServiceModule()}):
        results = memory_engine.recall_episodic_memory(
            query_text="sqlite wal deadlock",
            workspace_dir=ws_dir,
            top_k=3,
            db_path=db_path
        )

        assert embedding_calls == [], f"Expected 0 embedding_service calls, got {embedding_calls}"
        assert isinstance(results, list), "Recall result must be a list"
        assert len(results) > 0, "Expected at least one matching memory record via FTS5 BM25 fallback"

        match_dict = dict(results[0]) if hasattr(results[0], "keys") else results[0]
        assert match_dict.get("problem_signature") == "sqlite wal deadlock" or "sqlite wal deadlock" in str(match_dict)


def test_spec2_workspace_scoped_dense_guard(tmp_path):
    """Test 5: Verify dense_embeddings guard is scoped per workspace_hash (wsA dense != wsB dense)."""
    import struct

    db_path = str(tmp_path / "test_scoped.db")
    ws_a = str(tmp_path / "ws_a")
    ws_b = str(tmp_path / "ws_b")
    Path(ws_a).mkdir(exist_ok=True)
    Path(ws_b).mkdir(exist_ok=True)

    conn = memory_schema.init_database(db_path)
    try:
        h_a = canonical_workspace_hash(ws_a)
        h_b = canonical_workspace_hash(ws_b)
        now = time.time()
        conn.execute(
            "INSERT INTO workspace_episodic_memory (memory_id,workspace_hash,workspace_path,memory_type,title,problem_signature,solution_payload,context_metadata,bilingual_tags,content_folded,status,last_accessed_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("memA", h_a, ws_a, "bugfix", "A", "unrelated topic", "sol A", "{}", "a", "unrelated topic", "Active", now, now),
        )
        conn.execute(
            "INSERT INTO workspace_episodic_memory (memory_id,workspace_hash,workspace_path,memory_type,title,problem_signature,solution_payload,context_metadata,bilingual_tags,content_folded,status,last_accessed_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("memB", h_b, ws_b, "bugfix", "B", "sqlite wal deadlock", "sol B", "{}", "b", "sqlite wal deadlock", "Active", now, now),
        )
        blob = struct.pack("<256f", *([0.1] * 256))
        conn.execute(
            "INSERT INTO dense_embeddings (memory_id,workspace_hash,model_name,dimensions,vector_blob,norm,updated_at) VALUES (?,?,?,?,?,?,?)",
            ("memA", h_a, "test", 256, blob, 1.6, "2026-11-16T00:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()

    embedding_calls = []

    class DummyEmbeddingServiceModule:
        def __getattr__(self, name):
            embedding_calls.append(name)
            raise RuntimeError("embedding_service must not be imported when target workspace has 0 dense rows")

    with patch.dict(sys.modules, {"embedding_service": DummyEmbeddingServiceModule()}):
        results = memory_engine.recall_episodic_memory(
            query_text="sqlite wal deadlock",
            workspace_dir=ws_b,
            top_k=3,
            db_path=db_path,
        )
        assert embedding_calls == [], f"Expected 0 embedding_service calls for ws_b, got {embedding_calls}"
        assert len(results) == 1
        assert results[0]["trace"]["problem_signature"] == "sqlite wal deadlock"

    ws_a_calls = []

    class PositiveEmbeddingServiceModule:
        @staticmethod
        def get_embedding(text, is_query=True):
            ws_a_calls.append((text, is_query))
            return [0.1] * 256

    with patch.dict(sys.modules, {"embedding_service": PositiveEmbeddingServiceModule()}):
        ws_a_results = memory_engine.recall_episodic_memory(
            query_text="unrelated topic",
            workspace_dir=ws_a,
            top_k=3,
            db_path=db_path,
        )
        assert len(ws_a_calls) == 1, f"Expected 1 embedding_service call for ws_a, got {ws_a_calls}"
        assert len(ws_a_results) == 1
        assert ws_a_results[0]["trace"]["id"] == "memA"


def test_worker_delegation_policy_alignment():
    """Verify F2-F5 delegation policy alignment across rules/AGENTS.md and runtime hook_runner."""
    repo_root = get_repo_root()
    agents_md = (repo_root / "rules" / "AGENTS.md").read_text(encoding="utf-8")
    preflight = hook_runner.build_preflight_message({})

    canonical_tools = (
        "gemini_fast_edit",
        "gemini_generate_tests",
        "gemini_autonomous_loop",
        "gemini_execute_plan",
        "gemini_heavy_code_gen",
        "gemini_multimodal_vision",
        "gemini_argon_solve",
    )
    for text in (agents_md, preflight):
        assert "<=15" in text and ">15" in text
        assert "primarily as Architect" in text
        assert "on worker timeout or syntax error" in text
        for tool in canonical_tools:
            assert tool in text, f"Missing canonical tool {tool} in policy surface"


def test_read_only_live_wal_and_corrupt_quarantine_guard(tmp_path):
    """Verify OMNI_READ_ONLY=1 sees live uncheckpointed WAL data and skips .corrupt.*.bak writes."""
    import resolver
    from omni_graph import storage as graph_storage

    # 1. Live WAL on omni_graph DB (writer holds uncheckpointed WAL)
    gws = tmp_path / "live_graph_ws"
    gws.mkdir()
    w_gconn = graph_storage.init_db(gws)
    w_gconn.execute("PRAGMA wal_autocheckpoint = 0;")
    w_gconn.execute(
        "INSERT INTO codebase_files_meta (file_path, display_path, sha256, mtime, size_bytes, parsed_at, parse_status) VALUES (?,?,?,?,?,?,?)",
        ("f.py", "f.py", "abc", 1.0, 10, 1.0, "ok"),
    )
    w_gconn.execute(
        "INSERT INTO nodes (id, name, qualified_name, file_path, display_path, line_number, end_line_number, node_type) VALUES (?,?,?,?,?,?,?,?)",
        ("n1", "live_fn", "f.live_fn", "f.py", "f.py", 1, 2, "function"),
    )
    w_gconn.commit()

    # 2. Live WAL on omni_memory DB (writer holds uncheckpointed WAL)
    mws = tmp_path / "live_mem_ws"
    mws.mkdir()
    mdb = tmp_path / "live_mem.db"
    w_mconn = memory_schema.init_database(str(mdb))
    w_mconn.execute("PRAGMA wal_autocheckpoint = 0;")
    w_mconn.execute(
        "INSERT INTO workspace_episodic_memory (memory_id,workspace_hash,workspace_path,memory_type,title,problem_signature,solution_payload,context_metadata,bilingual_tags,content_folded,status,last_accessed_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("m-live", canonical_workspace_hash(str(mws)), str(mws), "bugfix", "Live WAL", "live wal signal", "use mode=ro", "{}", "wal", "live wal signal", "Active", time.time(), time.time()),
    )
    w_mconn.commit()

    # 3. Corrupt JSON files must not emit .corrupt.*.bak under OMNI_READ_ONLY=1
    corrupt_aff = tmp_path / "learned_affinities.json"
    corrupt_aff.write_text("{corrupt", encoding="utf-8")
    corrupt_reg = tmp_path / "registry.json"
    corrupt_reg.write_text("{corrupt", encoding="utf-8")

    try:
        with patch.dict(os.environ, {"OMNI_READ_ONLY": "1"}):
            ro_gconn = graph_storage.get_connection(gws, read_only=True, timeout_ms=500)
            try:
                assert ro_gconn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 1
            finally:
                ro_gconn.close()
            recs = memory_engine.recall_episodic_memory("live wal signal", workspace_dir=str(mws), top_k=3, db_path=str(mdb))
            assert len(recs) == 1 and recs[0]["trace"]["id"] == "m-live"
            resolver.load_learned_affinities(str(corrupt_aff))
            with patch("indexer.build_index", return_value={"skills": []}):
                resolver.load_registry(str(corrupt_reg))
        assert list(tmp_path.glob("*.corrupt.*.bak")) == []
    finally:
        w_gconn.close()
        w_mconn.close()
