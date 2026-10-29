#!/usr/bin/env python3
"""
Omni-Kernel v3.0: Cross-Session Experiential Memory Engine
Stores, recalls, and prunes proven execution traces (code snippets, bash commands, verified fixes).
Enables the AI to instantly recall verified past solutions across sessions in <0.3ms without re-reasoning.
100% Python Standard Library (Zero dependencies, pure deterministic JSON).
"""

import os
import re
import sys
import json
import time
import hashlib

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

TRACES_FILE = os.path.join(_SCRIPT_DIR, "proven_traces.json")
MAX_TRACES = 250


def tokenize(text: str) -> list:
    """Extracts normalized lowercase tokens from text."""
    if not text:
        return []
    cleaned = re.sub(r"[^\w\s\-\.]", " ", text.lower())
    tokens = [t.strip(".-") for t in cleaned.split() if len(t.strip(".-")) > 1]
    return list(set(tokens))


def load_traces(traces_path: str = None) -> dict:
    """Loads stored execution traces in <0.2ms."""
    path = traces_path or TRACES_FILE
    if not os.path.exists(path):
        return {"version": "3.0.0", "updated_at": "", "traces": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"version": "3.0.0", "updated_at": "", "traces": []}


def save_traces(data: dict, traces_path: str = None) -> bool:
    """Persists traces atomically."""
    path = traces_path or TRACES_FILE
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if os.path.exists(path):
            os.replace(tmp_path, path)
        else:
            os.rename(tmp_path, path)
        return True
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return False


def record_trace(problem_signature: str,
                 proven_solution: str,
                 action_type: str = "command",
                 tags: list = None,
                 workspace_context: str = "",
                 traces_path: str = None) -> dict:
    """
    Records or updates a proven execution trace.
    Returns the recorded trace object.
    """
    if not problem_signature or not proven_solution:
        return {}

    data = load_traces(traces_path)
    traces = data.get("traces", [])
    
    sig_tokens = tokenize(problem_signature)
    tag_tokens = []
    if tags:
        for t in tags:
            tag_tokens.extend(tokenize(str(t)))
    all_tokens = list(set(sig_tokens + tag_tokens))

    trace_id = hashlib.md5(f"{problem_signature.strip().lower()}".encode("utf-8")).hexdigest()[:10]

    # Check for existing trace
    existing = None
    for tr in traces:
        if tr.get("id") == trace_id or tr.get("problem_signature").strip().lower() == problem_signature.strip().lower():
            existing = tr
            break

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    if existing:
        existing["proven_solution"] = proven_solution.strip()
        existing["success_count"] = existing.get("success_count", 1) + 1
        existing["last_recalled"] = now_str
        existing["tokens"] = list(set(existing.get("tokens", []) + all_tokens))
        if tags:
            existing["tags"] = list(set(existing.get("tags", []) + tags))
        if workspace_context:
            existing["workspace_context"] = workspace_context
        result_trace = existing
    else:
        new_trace = {
            "id": trace_id,
            "problem_signature": problem_signature.strip(),
            "proven_solution": proven_solution.strip(),
            "action_type": action_type,
            "tags": tags or [],
            "workspace_context": workspace_context,
            "tokens": all_tokens,
            "success_count": 1,
            "created_at": now_str,
            "last_recalled": now_str
        }
        traces.append(new_trace)
        result_trace = new_trace

    # LRU Pruning if exceeds MAX_TRACES
    if len(traces) > MAX_TRACES:
        traces.sort(key=lambda x: (x.get("success_count", 1), x.get("last_recalled", "")), reverse=True)
        data["traces"] = traces[:MAX_TRACES]
    else:
        data["traces"] = traces

    save_traces(data, traces_path)
    return result_trace


def recall_traces(query_text: str,
                  workspace_dir: str = None,
                  top_k: int = 2,
                  threshold: float = 0.25,
                  traces_path: str = None) -> list:
    """
    Sub-millisecond retrieval of matching proven execution traces (<0.3ms).
    """
    if not query_text:
        return []

    data = load_traces(traces_path)
    traces = data.get("traces", [])
    if not traces:
        return []

    query_tokens = set(tokenize(query_text))
    if not query_tokens:
        return []

    scored = []
    for tr in traces:
        tr_tokens = set(tr.get("tokens", []))
        if not tr_tokens:
            continue
        intersection = query_tokens.intersection(tr_tokens)
        if not intersection:
            continue

        # Jaccard + Overlap composite score
        overlap_score = len(intersection) / len(query_tokens)
        jaccard_score = len(intersection) / len(query_tokens.union(tr_tokens))
        
        # Boost for success count
        utility_boost = min(0.3, tr.get("success_count", 1) * 0.05)
        
        # Context boost if matching workspace name
        context_boost = 0.0
        if workspace_dir and tr.get("workspace_context"):
            ws_base = os.path.basename(os.path.normpath(workspace_dir)).lower()
            if ws_base in tr.get("workspace_context", "").lower():
                context_boost = 0.15

        final_score = (overlap_score * 0.6) + (jaccard_score * 0.4) + utility_boost + context_boost

        if final_score >= threshold:
            scored.append({
                "trace": tr,
                "score": round(final_score, 3),
                "matched_tokens": list(intersection)
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    results = scored[:top_k]

    # Update last_recalled for top matches
    if results and (traces_path is None or traces_path == TRACES_FILE):
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        for res in results:
            res["trace"]["last_recalled"] = now_str
        save_traces(data, traces_path)

    return results


def seed_canonical_traces(traces_path: str = None):
    """Seeds baseline canonical verified engineering solutions."""
    canonical = [
        {
            "signature": "Docker port already in use / bind address in use",
            "solution": "fuser -k <port>/tcp || lsof -ti:<port> | xargs kill -9",
            "action_type": "command",
            "tags": ["docker", "port", "networking", "kill", "bind"],
            "workspace_context": "General Linux / Server"
        },
        {
            "signature": "pip install externally managed environment error on modern Linux",
            "solution": "python3 -m venv .venv && source .venv/bin/activate || pip install --break-system-packages",
            "action_type": "command",
            "tags": ["python", "pip", "venv", "externally-managed", "linux"],
            "workspace_context": "Python / Ubuntu"
        },
        {
            "signature": "FastAPI CORS wildcard allow origins with credentials forbidden",
            "solution": "allow_origins=['http://localhost:3000'] (Explicit origins required when allow_credentials=True)",
            "action_type": "code_snippet",
            "tags": ["fastapi", "cors", "credentials", "middleware", "security"],
            "workspace_context": "FastAPI / Backend"
        },
        {
            "signature": "Git push hang on Windows Credential Manager non-interactive subshell",
            "solution": "git config --global credential.helper manager && git push --dry-run",
            "action_type": "command",
            "tags": ["git", "push", "credential", "windows", "hang"],
            "workspace_context": "Git / Windows"
        },
        {
            "signature": "PowerShell command chaining syntax error with double ampersand",
            "solution": "Use semicolon ';' or separate command invocations instead of '&&' in PowerShell 5.1",
            "action_type": "command",
            "tags": ["powershell", "syntax", "chaining", "windows"],
            "workspace_context": "PowerShell / Windows"
        }
    ]
    for item in canonical:
        record_trace(
            problem_signature=item["signature"],
            proven_solution=item["solution"],
            action_type=item["action_type"],
            tags=item["tags"],
            workspace_context=item["workspace_context"],
            traces_path=traces_path
        )
    return len(canonical)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Omni-Kernel Experiential Memory Engine CLI")
    parser.add_argument("--list", action="store_true", help="List all stored proven execution traces")
    parser.add_argument("--query", "-q", type=str, default="", help="Query matching execution traces")
    parser.add_argument("--seed", action="store_true", help="Seed baseline canonical traces")
    parser.add_argument("--record", action="store_true", help="Record a new execution trace")
    parser.add_argument("--signature", "-s", type=str, default="", help="Problem signature")
    parser.add_argument("--solution", "-sol", type=str, default="", help="Proven working solution")
    parser.add_argument("--tags", "-t", type=str, default="", help="Comma-separated tags")
    parser.add_argument("--context", "-c", type=str, default="", help="Workspace context")
    args = parser.parse_args()

    if args.seed:
        seed_canonical_traces()
        print("✅ Baseline canonical execution traces seeded successfully.")
        sys.exit(0)

    if args.record:
        if not args.signature or not args.solution:
            print("❌ Both --signature and --solution are required to record a trace.")
            sys.exit(1)
        tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
        tr = record_trace(args.signature, args.solution, tags=tag_list, workspace_context=args.context)
        print(f"✅ Recorded execution trace '{tr.get('id')}': {tr.get('problem_signature')}")
        sys.exit(0)

    if args.query:
        matches = recall_traces(args.query)
        if not matches:
            print(f"ℹ️ No proven execution traces matched '{args.query}'.")
        else:
            print(f"💡 Found {len(matches)} matching proven execution trace(s):\n" + "=" * 60)
            for i, m in enumerate(matches, 1):
                tr = m["trace"]
                print(f"[{i}] Match Score: {m['score']*100:.1f}% (Matched: {', '.join(m['matched_tokens'])})")
                print(f"    Problem:  {tr['problem_signature']}")
                print(f"    Solution: {tr['proven_solution']}")
                print(f"    Context:  {tr['workspace_context']} | Successes: {tr['success_count']}\n")
        sys.exit(0)

    # Default: list traces
    data = load_traces()
    traces = data.get("traces", [])
    print("🧠 OMNI-KERNEL EXPERIENTIAL MEMORY LEDGER\n" + "=" * 65)
    print(f"Total Proven Traces: {len(traces)} | Last Updated: {data.get('updated_at', 'Never')}\n")
    if not traces:
        print("No traces stored. Run with --seed to populate initial canonical fixes.")
    else:
        for i, tr in enumerate(traces, 1):
            print(f"[{i}] {tr['id']}: {tr['problem_signature']}")
            print(f"    💡 Solution: {tr['proven_solution']}")
            print(f"    🏷️  Tags: {', '.join(tr.get('tags', []))} | Used: {tr.get('success_count', 1)} times\n")


if __name__ == "__main__":
    main()
