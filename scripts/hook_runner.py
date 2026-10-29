#!/usr/bin/env python3
"""
Omni-Kernel v2.5: Global PreInvocation Lifecycle Hook Runner
Processes Antigravity PreInvocation events:
- Reads stdin JSON (lastUserInput, workspacePaths, etc.)
- Resolves intent JIT via Omni-Kernel Unified Resolver
- Injects ephemeral cognitive pre-flight block (Skills, Inferred Rules, MCPs, Lợi/Hại/Đủ/Thiếu)
- Fail-safe: Always outputs valid JSON to stdout; exits 0 in <50ms.
"""

import os
import sys
import json

# Ensure scripts directory is on sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# Conversational fillers that do not require full pre-flight injection
TRIVIAL_FILLERS = {
    "ok", "oke", "okay", "yes", "y", "uh", "um", "yep", "sure",
    "tiếp tục", "tiep tuc", "cảm ơn", "cam on", "thanks", "thx", "ty",
    "được rồi", "duoc roi", "done", "xong", "rồi", "roi", "tiếp", "tiep",
    "chạy đi", "chay di", "làm đi", "lam di", "bắt đầu", "bat dau"
}


def build_preflight_message(resolution: dict) -> str:
    """Formats the cognitive pre-flight resolution into a clean, markdown block."""
    lines = ["[OMNI-KERNEL v2.5 PRE-FLIGHT ACTIVATION]"]
    
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
            
    # 3. Suggested MCP Tool Drivers
    mcps = resolution.get("suggested_mcp", [])
    if mcps:
        lines.append("\n🔌 Suggested MCP Tool Drivers:")
        for m in mcps:
            lines.append(f"  - {m}")
            
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

    return "\n".join(lines)


def process_hook(payload: dict) -> dict:
    """Core hook processing logic."""
    user_input = (payload.get("lastUserInput") or "").strip()
    
    # Skip empty input, slash commands, or trivial conversational fillers
    if not user_input:
        return {"injectSteps": []}
    if user_input.startswith("/"):
        return {"injectSteps": []}
    
    clean_lower = user_input.lower().strip("!.?, \t\n\r")
    if clean_lower in TRIVIAL_FILLERS or len(clean_lower) <= 2:
        return {"injectSteps": []}
    
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
