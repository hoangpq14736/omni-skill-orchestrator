#!/usr/bin/env python3
"""
Omni-Kernel v3.0: Global PreInvocation Lifecycle Hook Runner
Processes Antigravity PreInvocation events:
- Reads stdin JSON (lastUserInput, workspacePaths, etc.)
- Resolves intent JIT via Omni-Kernel Unified Resolver
- Injects ephemeral cognitive pre-flight block (Skills, Inferred Rules, MCPs, Lợi/Hại/Đủ/Thiếu)
- Fail-safe: Always outputs valid JSON to stdout; exits 0 in <50ms.
"""

import os
import sys
import json
import re
import sqlite3
import subprocess
import datetime

# Ensure scripts directory is on sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_utils import canonical_workspace_hash

LAST_ACTIVATION_PATH = os.path.join(_SCRIPT_DIR, "last_activation.json")
ACTIVATIONS_HISTORY_PATH = os.path.join(_SCRIPT_DIR, "activations_history.jsonl")

# Conversational fillers pattern with full-sentence boundary matching (<1.0ms fast-exit)
# Prevents false-positive suppression on prompts starting with filler words like "ok, please fix..."
FILLER_PATTERN = re.compile(
    r"^((ok|oke|okay|tiếp tục|tiep tuc|done|thanks|cảm ơn|cam on|chạy đi|chay di|yes|no|got it|sure)[.!\s,]*)+$",
    re.IGNORECASE
)


def build_preflight_message(resolution: dict) -> str:
    """Formats the cognitive pre-flight resolution into a clean, markdown block."""
    lines = ["[OMNI-KERNEL v3.0 PRE-FLIGHT ACTIVATION]"]
    
    # 1. Top Skills
    skills = resolution.get("skills", [])
    if skills:
        lines.append("🎯 JIT Skill Directives:")
        for item in skills[:3]:
            sk = item.get("skill", {})
            name = sk.get("name", "unknown")
            ver = sk.get("version", "1.0.0")
            path = sk.get("path", "")
            desc = sk.get("description", "")
            if len(desc) > 120:
                desc = desc[:117] + "..."
            lines.append(f"  * {name} (v{ver}) -> {path}")
            if desc:
                lines.append(f"    Instruction: {desc}")
    
    # 2. Inferred Domain Rules
    rules = resolution.get("inferred_rules", [])
    if rules:
        lines.append("\n🛡️ Mandatory Inferred Domain Rules:")
        for r in rules:
            lines.append(f"  - {r}")
            
    # 3. Suggested MCP Tool Drivers & Dynamic Virtual Bus
    mcps = resolution.get("suggested_mcp", [])
    mcp_tools = resolution.get("mcp_tools", [])
    if mcps or mcp_tools:
        lines.append("\n🔌 Omni-MCP Virtual Bus (Tool Gateway):")
        for m in mcps:
            lines.append(f"  - Server Driver: {m}")
        for mt in mcp_tools:
            lines.append(f"  * Dynamic Tool: {mt['server']}:{mt['tool']} -> {mt['description']}")
            if mt.get("properties"):
                lines.append(f"    Parameters: {', '.join(mt['properties'])}")
            
    # 4. Cognitive Pre-Flight Assessment (Lợi - Hại - Đủ - Thiếu)
    cpf = resolution.get("cognitive_pre_flight", {})
    if cpf:
        lines.append("\n🧠 Cognitive Pre-Flight Assessment (Tư duy 4 trục):")
        loi = cpf.get("loi_value", "")
        if loi:
            lines.append(f"  * Lợi (Value): {loi}")
        hais = cpf.get("hai_risks", [])
        if hais:
            lines.append(f"  * Hại (Risks): {'; '.join(hais)}")
        dus = cpf.get("du_completeness", [])
        if dus:
            lines.append(f"  * Đủ (Completeness): {'; '.join(dus)}")
        thieu = cpf.get("thieu_implicit", {})
        if thieu:
            mand = thieu.get("mandatory_inferred_rules", [])
            if mand:
                lines.append(f"  * Thiếu (Implicit Needs): Enforce {len(mand)} mandatory guardrails.")

    # 5. Proven Execution Traces (Cross-Session Experiential Memory)
    traces = resolution.get("proven_traces", [])
    if traces:
        lines.append("\n💡 Proven Execution Memory (Ký ức Thực nghiệm Đã kiểm chứng):")
        for item in traces:
            tr = item.get("trace", {})
            sol = tr.get("proven_solution", "")
            sig = tr.get("problem_signature", "")
            score = int(item.get("score", 0) * 100)
            lines.append(f"  * Proven Fix: {sol}")
            lines.append(f"    (Verified fix for '{sig}', Match: {score}%)")

    # 6. Active Hardware & Worker Fleet Directives
    lines.append("\n🤖 Active Hardware & Worker Fleet Directives:")
    lines.append("  * local_worker_mi50: AMD Instinct MI50 (Vega 20, 16GB HBM2 @ 1024 GB/s) via http://127.0.0.1:8080/v1 (48.5 tok/s, 16k context, SQLite/IPC/FastEdit)")
    lines.append("  * groq_worker_cloud: Groq LPU (openai/gpt-oss-120b) via Cloud API (300-800+ tok/s, pure algorithmic/transformation tasks)")

    # 7. Dual-Tier Cognitive Routing & Quota Guard
    tier_info = resolution.get("tier_assessment", {})
    tier = tier_info.get("tier", 1)
    tier_name = tier_info.get("tier_name", "L1 Reflex")
    factors = tier_info.get("factors", [])
    if tier == 2:
        lines.append("\n⚡ Dual-Tier Routing: Tier 2 (Deep Deliberation) | 'omni-strategist' Subagent Approved")
        if factors:
            lines.append(f"   Complexity Factors: {'; '.join(factors)}")
    else:
        lines.append("\n⚡ Dual-Tier Routing: Tier 1 (Fast Reflex) | Quota Guard Active (0-Token Mode)")

    # 8. Model Transparency & User Observability Directive
    top_skill_name = skills[0].get("skill", {}).get("name", "generic") if skills else "generic"
    rule_count = len(rules)
    mcp_count = len(mcps)
    trace_count = len(traces)
    trace_badge = f" | Traces: [{trace_count} recalled]" if trace_count > 0 else ""
    lines.append("\n📢 Transparency Directive:")
    lines.append("Render a compact 1-line badge at the very beginning of your technical response:")
    lines.append(f"`⚡ Omni-Kernel: [{tier_name}] | Skill: [{top_skill_name}] | Rules: [{rule_count} active] | MCP: [{mcp_count} suggested]{trace_badge}`")

    return "\n".join(lines)


def process_hook(payload: dict) -> dict:
    """Core hook processing logic."""
    raw_user_input = (payload.get("lastUserInput") or payload.get("prompt") or payload.get("userInput") or "").strip()
    
    # Skip empty input or slash commands
    if not raw_user_input:
        return {"injectSteps": []}
    if raw_user_input.startswith("/"):
        return {"injectSteps": []}
    
    # T011: Full-sentence boundary matching for filler suppression (<1.0ms fast-exit)
    if FILLER_PATTERN.match(raw_user_input) or len(raw_user_input.strip("!.?, \t\n\r")) <= 2:
        return {"injectSteps": []}

    # T010: 2,048-char head clamping invariant
    user_input = raw_user_input[:2048]
    
    # Extract workspace paths
    workspace_paths = payload.get("workspacePaths") or []
    workspace_dir = workspace_paths[0] if workspace_paths else os.getcwd()
    
    try:
        from resolver import resolve_skill
        resolution = resolve_skill(intent_text=user_input, workspace_dir=workspace_dir, unified=True)
    except Exception as e:
        # Fail gracefully with empty injectSteps if resolver encounters error
        return {"injectSteps": []}
    
    # If no skills and no rules, do not inject
    if not resolution.get("skills") and not resolution.get("inferred_rules"):
        return {"injectSteps": []}

    skills = resolution.get("skills", [])
    
    # T014: Decouple synchronous file writes into l1_staging_log table with PRAGMA synchronous = NORMAL
    try:
        db_path = os.path.join(_SCRIPT_DIR, "..", "omni_memory.db")
        conn = sqlite3.connect(db_path, timeout=0.5)
        conn.execute("PRAGMA synchronous = NORMAL;")
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash, top_skill, tier_used, recalled_traces)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("sessionId", "session_default"),
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                user_input[:250],
                canonical_workspace_hash(workspace_dir),
                skills[0]["skill"]["name"] if skills else "none",
                resolution.get("tier_assessment", {}).get("tier", 1),
                json.dumps([t.get("trace", {}).get("id") for t in resolution.get("proven_traces", [])])
            )
        )
        last_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Argon Chốt chặn 1: Lazy Threshold Detach (Không treo Pipe, 0% bão spawn)
        if last_id and (last_id % 50 == 0):
            try:
                consolidator_script = os.path.join(_SCRIPT_DIR, "consolidator.py")
                subprocess.Popen(
                    [sys.executable, consolidator_script, "--batch-run"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            except Exception:
                pass
    except Exception:
        pass

    # Record telemetry to last_activation.json for user observability and CLI inspection
    try:
        record = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_input": user_input,
            "workspace_dir": workspace_dir,
            "top_skill": skills[0]["skill"]["name"] if skills else "none",
            "skills": [
                {
                    "name": s.get("skill", {}).get("name"),
                    "version": s.get("skill", {}).get("version"),
                    "source_type": s.get("skill", {}).get("source_type"),
                    "raw_score": round(s.get("raw_score", 0), 1),
                    "arbitration_reason": s.get("arbitration_reason", "")
                } for s in skills[:3]
            ],
            "inferred_rules": resolution.get("inferred_rules", []),
            "suggested_mcp": resolution.get("suggested_mcp", []),
            "cognitive_pre_flight": resolution.get("cognitive_pre_flight", {}),
            "tier_assessment": resolution.get("tier_assessment", {}),
            "proven_traces": resolution.get("proven_traces", [])
        }
        with open(LAST_ACTIVATION_PATH, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)

        # Append compact event to activations_history.jsonl
        history_entry = {
            "timestamp": record["timestamp"],
            "user_input": record["user_input"][:150],
            "workspace_dir": record["workspace_dir"],
            "top_skill": record["top_skill"],
            "tier": record.get("tier_assessment", {}).get("tier", 1),
            "tier_name": record.get("tier_assessment", {}).get("tier_name", "L1 Reflex"),
            "rules_count": len(record.get("inferred_rules", [])),
            "mcp_count": len(record.get("suggested_mcp", [])),
            "traces_count": len(record.get("proven_traces", []))
        }
        with open(ACTIVATIONS_HISTORY_PATH, "a", encoding="utf-8") as hf:
            hf.write(json.dumps(history_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

    message_text = build_preflight_message(resolution)
    
    return {
        "injectSteps": [
            {
                "ephemeralMessage": message_text
            }
        ]
    }


def main():
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}
        
    try:
        output = process_hook(payload)
    except Exception:
        output = {"injectSteps": []}
        
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
