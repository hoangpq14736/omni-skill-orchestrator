#!/usr/bin/env python3
"""Unified CLI Driver for Omni-Graph (Graphify Core Engine)."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Adjust path to import scripts.omni_graph
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from omni_graph.storage import (
    get_connection,
    init_db,
    delete_file_records,
    clean_orphan_edges,
    record_file_parsed,
    batch_insert_nodes,
    batch_insert_signatures,
    batch_insert_edges,
    batch_insert_lifecycle_hooks,
)
from omni_graph.git_hygiene import ensure_git_hygiene
from omni_graph.fingerprint import (
    detect_dirty_files,
    scan_workspace_files,
    compute_sha256,
)
from omni_graph.visitor import parse_source_file, parse_python_file
from omni_graph.validator import validate_call_site
from omni_graph.lifecycle import LifecycleRegistrationGuard
from omni_graph.traversal import compute_blast_radius
from omni_graph.visualizer import generate_graph_html
from omni_graph.self_healing import micro_index_file

def _exit(code: int, msg: str = "") -> None:
    if msg:
        print(msg, file=sys.stderr)
    sys.exit(code)

def _load_json(text: str):
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        _exit(2, f"Invalid JSON string: {exc}")

def scan_workspace(workspace_root: Path, force_full: bool = False) -> dict:
    start_time = time.time()
    ensure_git_hygiene(workspace_root)

    conn = get_connection(workspace_root)
    init_db(conn)

    dirty_info = detect_dirty_files(conn, workspace_root)
    dirty_files = dirty_info["dirty"]
    deleted_files = dirty_info["deleted"]

    if force_full:
        all_scanned = scan_workspace_files(workspace_root)
        dirty_files = all_scanned
        for item in dirty_files:
            item["sha256"] = compute_sha256(item["abs_path"])

    stats = {
        "files_processed": 0,
        "nodes": 0,
        "signatures": 0,
        "edges": 0,
        "lifecycle_hooks": 0,
        "deleted_files_purged": len(deleted_files),
        "unchanged": dirty_info["unchanged"] if not force_full else 0,
    }

    # Purge deleted files
    for del_file in deleted_files:
        delete_file_records(conn, del_file)

    for item in dirty_files:
        canon = item["canonical_path"]
        display = item["display_path"]
        abs_p = item["abs_path"]
        sha = item.get("sha256") or compute_sha256(abs_p)
        mtime = item["mtime"]
        size_bytes = item["size_bytes"]

        nodes, signatures, edges, hooks, parse_status, err_msg = parse_source_file(canon, display, abs_p)

        with conn:
            delete_file_records(conn, canon)
            record_file_parsed(
                conn, canon, display, sha, mtime, size_bytes,
                parse_status, len(nodes), len(edges), err_msg
            )
            if nodes:
                batch_insert_nodes(conn, nodes)
                stats["nodes"] += len(nodes)
            if signatures:
                batch_insert_signatures(conn, signatures)
                stats["signatures"] += len(signatures)
            if edges:
                batch_insert_edges(conn, edges)
                stats["edges"] += len(edges)
            if hooks:
                batch_insert_lifecycle_hooks(conn, hooks)
                stats["lifecycle_hooks"] += len(hooks)

            stats["files_processed"] += 1

    clean_orphan_edges(conn)
    conn.commit()
    conn.close()

    stats["elapsed_sec"] = time.time() - start_time
    return stats

def main() -> None:
    parser = argparse.ArgumentParser(description="Omni-Graph Unified Codebase Topology Engine.")
    parser.add_argument("--workspace", "-w", default=".", help="Target workspace root path (default: .)")
    parser.add_argument("--json", action="store_true", help="Format CLI output as JSON")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", "--index", action="store_true", help="Incremental workspace scan and topology indexing")
    group.add_argument("--rebuild", action="store_true", help="Force rebuild topology database from scratch")
    group.add_argument("--blast-radius", "-b", metavar="SYMBOL_OR_FILE", help="Calculate transitive blast radius impact")
    group.add_argument("--check-contract", action="store_true", help="Verify signature contract for a symbol call site")
    group.add_argument("--check-lifecycle", action="store_true", help="Detect unregistered/dangling lifecycle hooks")
    group.add_argument("--visualize", "-v", nargs="?", const="default", metavar="OUTPUT_HTML", help="Export standalone interactive HTML5 Canvas topology")

    parser.add_argument("--symbol", help="Target symbol or qualified function name for --check-contract")
    parser.add_argument("--kwargs", help="JSON dictionary of keyword arguments passed at call site")
    parser.add_argument("--args-count", type=int, default=0, help="Number of positional arguments passed at call site")

    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()

    if args.scan or args.rebuild:
        stats = scan_workspace(workspace, force_full=args.rebuild)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(f"⚡ Omni-Graph Scan Complete ({stats['elapsed_sec']:.3f}s):")
            print(f"  • Processed files: {stats['files_processed']}")
            print(f"  • Nodes: {stats['nodes']} | Signatures: {stats['signatures']} | Edges: {stats['edges']}")
            print(f"  • Lifecycle hooks: {stats['lifecycle_hooks']} | Unchanged files: {stats['unchanged']}")
        sys.exit(0)

    conn = get_connection(workspace)

    if args.blast_radius:
        res = compute_blast_radius(conn, args.blast_radius)
        conn.close()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"\n⚡ Omni-Graph Blast Radius for '{args.blast_radius}':")
            print(f"  • Risk Level: {res['risk_level']} (Score: {res['risk_score']}/100)")
            print(f"  • Direct Callers ({len(res['direct_callers'])}):")
            for c in res['direct_callers'][:10]:
                print(f"      - {c['source_id']} ({c['relation_type']})")
            if len(res['direct_callers']) > 10:
                print(f"      ... and {len(res['direct_callers']) - 10} more")
            print(f"  • Impacted Files ({len(res['impacted_files'])}): {', '.join(res['impacted_files'][:5])}")
        sys.exit(0)

    if args.check_contract:
        if not args.symbol:
            _exit(2, "Error: --symbol is required for --check-contract")
        passed_kwargs = _load_json(args.kwargs) if args.kwargs else {}
        kw_list = list(passed_kwargs.keys()) if isinstance(passed_kwargs, dict) else list(passed_kwargs)

        res = validate_call_site(conn, args.symbol, args.args_count, kw_list)
        conn.close()

        if args.json:
            print(json.dumps({
                "symbol": args.symbol,
                "is_valid": res.is_valid,
                "error_code": res.error_code,
                "message": res.message,
                "suggested_fix": res.suggested_fix,
            }, indent=2))
        else:
            status_badge = "✅ VALID" if res.is_valid else f"❌ VIOLATION [{res.error_code}]"
            print(f"\n⚡ Omni-Graph Contract Check for '{args.symbol}': {status_badge}")
            if not res.is_valid:
                print(f"  • Reason: {res.message}")
                if res.suggested_fix:
                    print(f"  • Suggestion: {res.suggested_fix}")
        sys.exit(0 if res.is_valid else 1)

    if args.check_lifecycle:
        diags = LifecycleRegistrationGuard.check_lifecycle_registrations(conn, workspace)
        conn.close()
        unregistered = [d for d in diags if not d["is_registered"]]

        if args.json:
            print(json.dumps(diags, indent=2))
        else:
            print(f"\n⚡ Omni-Graph Lifecycle Registration Audit ({len(diags)} hooks checked):")
            if not unregistered:
                print("  ✅ All lifecycle hooks & commands are properly registered and synced!")
            else:
                print(f"  ⚠️ Found {len(unregistered)} unregistered/unsynced lifecycle hook(s):")
                for u in unregistered:
                    print(f"    - {u['hook_name']} at {u['file_path']}:{u['line_number']}")
                    print(f"      Issue: {u['message']}")
                    if u['suggested_fix']:
                        print(f"      Fix:   {u['suggested_fix']}")
        sys.exit(1 if unregistered else 0)

    if args.visualize is not None:
        out_p = None
        if args.visualize != "default" and args.visualize:
            out_p = Path(args.visualize)
        else:
            out_p = workspace / ".omni" / "graph.html"

        generate_graph_html(conn, out_p, title=f"Omni-Graph Topology: {workspace.name}")
        conn.close()
        print(f"⚡ Interactive topology visualizer generated: {out_p}")
        sys.exit(0)

if __name__ == "__main__":
    main()
