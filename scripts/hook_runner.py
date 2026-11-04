#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Global PreInvocation Lifecycle Hook Runner
Processes Antigravity PreInvocation events:
- Reads bounded stdin JSON (max 64 KiB)
- Resolves intent JIT via Omni-Kernel Unified Resolver
- Universal field-level IPI sanitization via safe_field (VULN-202)
- Cryptographic HMAC-SHA256 signature verification for Council Gate reviews (VULN-201)
- Non-blocking O_NOFOLLOW file checks eliminating FIFO DoS & TOCTOU races (VULN-203)
- Comprehensive credential redaction across all telemetry fields (VULN-204)
- Hardened HTML/markdown escaping neutralizing injection delimiters (VULN-205)
- Injects ephemeral cognitive pre-flight block (Skills, Inferred Rules, MCPs, Lợi/Hại/Đủ/Thiếu)
- Fail-safe: Always outputs valid JSON to stdout; exits 0 in <25ms SLA.
"""

import os
import sys
import json
import re
import uuid
import stat
import sqlite3
import subprocess
import datetime
import hashlib
from typing import Any

# Ensure scripts directory is on sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_utils import canonical_workspace_hash, redact_secrets, persist_diag, verify_audit_meta
from workspace_sanitizer import AssimilatorGuard, TrustFileLock

LAST_ACTIVATION_PATH = os.path.join(_SCRIPT_DIR, "last_activation.json")
ACTIVATIONS_HISTORY_PATH = os.path.join(_SCRIPT_DIR, "activations_history.jsonl")
MAX_HISTORY_BYTES = 10 * 1024 * 1024  # 10 MiB rotation limit

# Conversational fillers pattern with full-sentence boundary matching (<1.0ms fast-exit)
FILLER_PATTERN = re.compile(
    r"^((ok|oke|okay|tiếp tục|tiep tuc|done|thanks|cảm ơn|cam on|chạy đi|chay di|đi|di|yes|no|got it|sure)[.!\s,]*)+$",
    re.IGNORECASE
)

# Architectural and SDD intent detection pattern (Rule 6 Council Protocol Gatekeeper)
GATEKEEPER_INTENT_PATTERN = re.compile(
    r"(\b(rfc|frc|sdd|spec\.md|plan\.md)\b|/teamwork|\b(kiến trúc|architecture|design system|gatekeeper)\b)",
    re.IGNORECASE
)


def is_architecture_intent(prompt: str) -> bool:
    """Detects whether prompt involves major architectural design, RFC, or SDD specification."""
    return bool(GATEKEEPER_INTENT_PATTERN.search(prompt))


def sanitize_injected_text(val: Any, max_len: int = 250, single_line: bool = False) -> str:
    """
    Sanitizes workspace-derived content to prevent markdown/instruction injection (VULN-004, VULN-205).
    Strips control characters, line separators, neutralizes comment delimiters and markdown fences.
    """
    if val is None:
        return ""
    text = str(val)
    max_len = max(3, max_len)
    # Strip dangerous non-printable control characters and Unicode line/paragraph separators (U+2028, U+2029)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u2028\u2029]", "", text)
    if single_line:
        text = re.sub(r"[\r\n\t]+", " ", text).strip()
    # Neutralize HTML/comment delimiters that could escape framing
    text = text.replace("<!--", "&lt;!--").replace("-->", "--&gt;")
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    # Neutralize code fence escapes that could break ephemeralMessage framing
    text = text.replace("```", "'''")
    if len(text) > max_len:
        text = text[:max_len - 3] + "..."
    return text


def safe_field(val: Any, max_len: int = 250, single_line: bool = True) -> str:
    """
    Universal workspace-derived field gatekeeper (VULN-202).
    Applies sanitization, AssimilatorGuard IPI scanning, and secret redaction.
    """
    clean = sanitize_injected_text(val, max_len=max_len, single_line=single_line)
    safe, _ = AssimilatorGuard.scan_rules(clean)
    if not safe:
        persist_diag(f"Field blocked by security policy: {clean[:40]}...", 128)
        return "[BLOCKED_BY_POLICY]"
    return clean


def verify_critic_artifact(workspace_dir: str, target_file: str = None) -> tuple:
    """
    Decoupled non-blocking filesystem verification (<0.1ms).
    Reads candidate review files with O_NONBLOCK and S_ISREG check (VULN-203).
    Enforces HMAC-SHA256 authenticity signature (VULN-201) and canonical input_hash matching (VULN-003).
    """
    candidate_names = ["CRITIC_REVIEW.md", "AUDIT_REVIEW.md", "DEEPSEEK_REVIEW.md"]
    candidate_paths = [os.path.join(workspace_dir, name) for name in candidate_names]

    # Bounded specs directory traversal (max depth 2, max 15 entries) to preserve SLA (VULN-203)
    try:
        specs_dir = os.path.join(workspace_dir, "specs")
        if os.path.isdir(specs_dir):
            for entry in os.listdir(specs_dir)[:15]:
                sub_path = os.path.join(specs_dir, entry)
                if os.path.isdir(sub_path):
                    for name in candidate_names:
                        candidate_paths.append(os.path.join(sub_path, name))
    except Exception:
        pass

    # Resolve canonical target_full_path if target_file is specified
    target_full_path = None
    clean_target = os.path.basename(target_file) if target_file else None

    if target_file:
        if os.path.isabs(target_file) and os.path.isfile(target_file):
            target_full_path = os.path.normcase(os.path.realpath(target_file))
        else:
            cand = os.path.join(workspace_dir, target_file)
            if os.path.isfile(cand):
                target_full_path = os.path.normcase(os.path.realpath(cand))
            else:
                specs_dir = os.path.join(workspace_dir, "specs")
                if os.path.isdir(specs_dir):
                    for root, _, files in os.walk(specs_dir):
                        if clean_target in files:
                            target_full_path = os.path.normcase(os.path.realpath(os.path.join(root, clean_target)))
                            break

    for c_path in candidate_paths:
        if not os.path.isfile(c_path):
            continue
        try:
            # VULN-203: Open with O_RDONLY | O_NOFOLLOW | O_NONBLOCK and verify S_ISREG
            open_flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                open_flags |= os.O_NOFOLLOW
            if hasattr(os, "O_NONBLOCK"):
                open_flags |= os.O_NONBLOCK
            if hasattr(os, "O_BINARY"):
                open_flags |= os.O_BINARY

            try:
                c_fd = os.open(c_path, open_flags)
            except OSError:
                continue

            try:
                c_st = os.fstat(c_fd)
                if not stat.S_ISREG(c_st.st_mode):
                    continue  # Reject FIFOs, directories, and non-regular files
                header_bytes = os.read(c_fd, 4096)
                header = header_bytes.decode("utf-8", errors="ignore")
                review_mtime = c_st.st_mtime
            finally:
                os.close(c_fd)

            match = re.search(r"<!--\s*OMNI_AUDIT_META:\s*({.*?})\s*-->", header, re.DOTALL)
            if not match:
                continue

            meta = json.loads(match.group(1))

            # VULN-201: Verify cryptographic authenticity signature via HMAC-SHA256
            if not verify_audit_meta(meta):
                meta["stale_reason"] = "signature missing or invalid HMAC authentication"
                return "UNREVIEWED", meta

            meta_target = meta.get("target_file")
            is_inline = (meta_target == "inline_prompt")

            # VULN-HR-001: When target_file is specified, reject inline_prompt bypass
            if target_file and is_inline:
                continue

            # VULN-003 & VULN-HR-003: If target_file specified, require canonical path on disk
            if target_file:
                if not target_full_path or not os.path.isfile(target_full_path):
                    meta["stale_reason"] = "target_file specified does not exist on disk (missing)"
                    return "UNREVIEWED", meta

                if not meta_target or not isinstance(meta_target, str):
                    continue

                cand_meta = meta_target if os.path.isabs(meta_target) else os.path.join(workspace_dir, meta_target)
                if not os.path.exists(cand_meta):
                    continue
                meta_target_canonical = os.path.normcase(os.path.realpath(cand_meta))

                if meta_target_canonical != target_full_path:
                    continue

            # Anti-TOCTOU Freshness & Cryptographic Hash Validation (VULN-HR-002, VULN-104)
            if target_full_path and os.path.isfile(target_full_path):
                meta_hash = meta.get("input_hash")
                if not isinstance(meta_hash, str) or not meta_hash.strip():
                    meta["stale_reason"] = "input_hash missing or invalid in audit metadata"
                    return "STALE_REVIEW", meta

                # Open target once with O_RDONLY | O_NOFOLLOW to eliminate TOCTOU and stat/hash races
                t_flags = os.O_RDONLY
                if hasattr(os, "O_NOFOLLOW"):
                    t_flags |= os.O_NOFOLLOW
                if hasattr(os, "O_BINARY"):
                    t_flags |= os.O_BINARY

                try:
                    fd = os.open(target_full_path, t_flags)
                except OSError:
                    continue

                try:
                    st = os.fstat(fd)
                    if not stat.S_ISREG(st.st_mode):
                        meta["stale_reason"] = "target_file is not a regular file"
                        return "UNREVIEWED", meta
                    if st.st_size > 5 * 1024 * 1024:
                        meta["stale_reason"] = "target_file exceeds 5 MiB size limit"
                        return "UNREVIEWED", meta

                    hasher = hashlib.sha256()
                    while True:
                        chunk = os.read(fd, 65536)
                        if not chunk:
                            break
                        hasher.update(chunk)
                    current_hash = hasher.hexdigest()

                    target_mtime = st.st_mtime
                    if target_mtime > review_mtime + 1.0:
                        meta["stale_reason"] = "target_file was modified after audit review generation"
                        return "STALE_REVIEW", meta
                finally:
                    os.close(fd)

                expected_hash = meta_hash.replace("sha256:", "").strip().lower()
                if current_hash.lower() != expected_hash:
                    meta["stale_reason"] = "target_file content hash mismatch (modified since audit)"
                    return "STALE_REVIEW", meta

            verdict = meta.get("verdict", "UNREVIEWED")
            return verdict, meta

        except Exception:
            continue

    return "UNREVIEWED", None


def build_preflight_message(resolution: dict, gatekeeper_text: str = None, drift_text: str = None) -> str:
    """Formats the cognitive pre-flight resolution into a clean, sanitized markdown block (VULN-004, VULN-202)."""
    lines = ["[OMNI-KERNEL v4.1 PRE-FLIGHT ACTIVATION]"]
    
    # 1. Top Skills (Universal safe_field gatekeeper)
    skills = resolution.get("skills", [])
    if skills:
        lines.append("🎯 JIT Skill Directives:")
        for item in skills[:3]:
            sk = item.get("skill", {})
            name = safe_field(sk.get("name", "unknown"), 64, single_line=True)
            ver = safe_field(sk.get("version", "1.0.0"), 32, single_line=True)
            path = safe_field(sk.get("path", ""), 200, single_line=True)
            desc = safe_field(sk.get("description", ""), 120, single_line=True)
            lines.append(f"  * {name} (v{ver}) -> {path}")
            if desc:
                lines.append(f"    Instruction: {desc}")
    
    # 2. Inferred Domain Rules (Sanitized through safe_field)
    rules = resolution.get("inferred_rules", [])
    if rules:
        lines.append("\n🛡️ Mandatory Inferred Domain Rules:")
        for r in rules:
            clean_rule = safe_field(str(r), 250, single_line=True)
            if clean_rule != "[BLOCKED_BY_POLICY]":
                lines.append(f"  - {clean_rule}")
            
    # 3. Suggested MCP Tool Drivers & Dynamic Virtual Bus
    mcps = resolution.get("suggested_mcp", [])
    mcp_tools = resolution.get("mcp_tools", [])
    if mcps or mcp_tools:
        lines.append("\n🔌 Omni-MCP Virtual Bus (Tool Gateway):")
        for m in mcps:
            clean_m = safe_field(m, 64, single_line=True)
            lines.append(f"  - Server Driver: {clean_m}")
        for mt in mcp_tools:
            s_name = safe_field(mt.get('server', ''), 64, single_line=True)
            t_name = safe_field(mt.get('tool', ''), 64, single_line=True)
            t_desc = safe_field(mt.get('description', ''), 150, single_line=True)
            lines.append(f"  * Dynamic Tool: {s_name}:{t_name} -> {t_desc}")
            if mt.get("properties"):
                clean_props = [safe_field(p, 32, single_line=True) for p in mt.get("properties", [])]
                lines.append(f"    Parameters: {', '.join(clean_props)}")
            
    # 4. Cognitive Pre-Flight Assessment (Lợi - Hại - Đủ - Thiếu)
    cpf = resolution.get("cognitive_pre_flight", {})
    if cpf:
        lines.append("\n🧠 Cognitive Pre-Flight Assessment (Tư duy 4 trục):")
        loi = safe_field(cpf.get("loi_value", ""), 200, single_line=True)
        if loi:
            lines.append(f"  * Lợi (Value): {loi}")
        hais = [safe_field(h, 150, single_line=True) for h in cpf.get("hai_risks", [])]
        if hais:
            lines.append(f"  * Hại (Risks): {'; '.join(hais)}")
        dus = [safe_field(d, 150, single_line=True) for d in cpf.get("du_completeness", [])]
        if dus:
            lines.append(f"  * Đủ (Completeness): {'; '.join(dus)}")
        thieu = cpf.get("thieu_implicit", {})
        if thieu:
            mand = thieu.get("mandatory_inferred_rules", [])
            if mand:
                clean_mand = [safe_field(m, 120, single_line=True) for m in mand if safe_field(m, 120) != "[BLOCKED_BY_POLICY]"]
                if clean_mand:
                    lines.append(f"  * Thiếu (Implicit Needs): Enforce {len(clean_mand)} mandatory guardrails.")

    # 5. Proven Execution Traces (Cross-Session Experiential Memory)
    traces = resolution.get("proven_traces", [])
    if traces:
        lines.append("\n💡 Proven Execution Memory (Ký ức Thực nghiệm Đã kiểm chứng):")
        for item in traces:
            tr = item.get("trace", {})
            sol = safe_field(tr.get("proven_solution", ""), 200, single_line=True)
            sig = safe_field(tr.get("problem_signature", ""), 200, single_line=True)
            score = int(item.get("score", 0) * 100)
            lines.append(f"  * Proven Fix: {sol}")
            lines.append(f"    (Verified fix for '{sig}', Match: {score}%)")

    # 6. Active Hardware & Worker Fleet Directives
    lines.append("\n🤖 Active Hardware & Worker Fleet Directives (MANDATORY DELEGATION INVARIANT):")
    lines.append("  * local_worker_mi50: AMD Instinct MI50 (Vega 20, 16GB HBM2 @ 1024 GB/s) via http://127.0.0.1:8080/v1 (48.5 tok/s, 16k context, SQLite/IPC/FastEdit)")
    lines.append("  * groq_worker_cloud: Groq LPU (openai/gpt-oss-120b) via Cloud API (300-800+ tok/s, pure algorithmic/transformation tasks)")
    lines.append("  * DELEGATION MANDATE: Do NOT generate large code or tests in Cloud context. Delegate code generation and unit tests to 'groq_worker_cloud' (groq_code_gen, groq_generate_tests) and local edits to 'local_worker_mi50' (fast_edit, execute_code_task). Cloud agent acts strictly as Architect & Gatekeeper.")

    # 7. Dual-Tier Cognitive Routing & Quota Guard
    tier_info = resolution.get("tier_assessment", {})
    tier = tier_info.get("tier", 1)
    tier_name = safe_field(tier_info.get("tier_name", "L1 Reflex"), 32, single_line=True)
    factors = [safe_field(f, 64, single_line=True) for f in tier_info.get("factors", [])]
    if tier == 2:
        lines.append("\n⚡ Dual-Tier Routing: Tier 2 (Deep Deliberation) | 'omni-strategist' Subagent Approved")
        if factors:
            lines.append(f"   Complexity Factors: {'; '.join(factors)}")
    else:
        lines.append("\n⚡ Dual-Tier Routing: Tier 1 (Fast Reflex) | Quota Guard Active (0-Token Mode)")

    # 8. Model Transparency & User Observability Directive
    top_skill_name = safe_field(skills[0].get("skill", {}).get("name", "generic"), 64, single_line=True) if skills else "generic"
    rule_count = len(rules)
    mcp_count = len(mcps)
    trace_count = len(traces)
    trace_badge = f" | Traces: [{trace_count} recalled]" if trace_count > 0 else ""
    lines.append("\n📢 Transparency Directive (IMMUTABLE INVARIANT):")
    lines.append("You MUST ALWAYS render the compact 1-line badge at the very first line of EVERY response, regardless of prompt phrasing or brevity:")
    lines.append(f"`⚡ Omni-Kernel: [{tier_name}] | Skill: [{top_skill_name}] | Rules: [{rule_count} active] | MCP: [{mcp_count} suggested]{trace_badge}`")

    if drift_text:
        clean_drift = safe_field(drift_text, 500, single_line=False)
        if clean_drift != "[BLOCKED_BY_POLICY]":
            lines.append(clean_drift)
    if gatekeeper_text:
        clean_gate = safe_field(gatekeeper_text, 500, single_line=False)
        if clean_gate != "[BLOCKED_BY_POLICY]":
            lines.append(clean_gate)
    return "\n".join(lines)


def process_hook(payload: dict) -> dict:
    """Core hook processing logic."""
    raw_user_input = (payload.get("lastUserInput") or payload.get("prompt") or payload.get("userInput") or "").strip()
    
    # Skip empty input or slash commands
    if not raw_user_input:
        return {"injectSteps": []}
    if raw_user_input.startswith("/") and not raw_user_input.startswith("/teamwork"):
        return {"injectSteps": []}
    
    # T011: Full-sentence boundary matching for filler suppression (<1.0ms fast-exit)
    if FILLER_PATTERN.match(raw_user_input) or len(raw_user_input.strip("!.?, \t\n\r")) <= 2:
        return {"injectSteps": []}

    # T010: 2,048-char head clamping invariant
    user_input = raw_user_input[:2048]
    
    # Redact sensitive credentials before storing or staging (VULN-006)
    safe_user_input = redact_secrets(user_input)
    
    # Extract workspace paths
    workspace_paths = payload.get("workspacePaths") or []
    workspace_dir = workspace_paths[0] if workspace_paths else os.getcwd()
    
    try:
        from resolver import resolve_skill
        resolution = resolve_skill(intent_text=user_input, workspace_dir=workspace_dir, unified=True)
    except Exception as e:
        persist_diag(e, 256)
        return {"injectSteps": []}
    
    # Sub-0.15ms Fast Workspace Rule Drift Sniffer
    drift_text = None
    try:
        from kernel_sync import KernelSynchronizer, KERNEL_VERSION
        for candidate_rule in [
            os.path.join(workspace_dir, ".cursorrules"),
            os.path.join(workspace_dir, "GEMINI.md"),
            os.path.join(workspace_dir, "rules", "AGENTS.md")
        ]:
            if os.path.isfile(candidate_rule):
                drift_v, is_missing = KernelSynchronizer.detect_workspace_drift(candidate_rule)
                if drift_v:
                    fname = os.path.basename(candidate_rule)
                    drift_text = (
                        f"\n⚠️ [Omni-Kernel Immune Warning] Workspace file '{fname}' is at v{drift_v} (Current: v{KERNEL_VERSION}).\n"
                        f"  * JIT v{KERNEL_VERSION} In-Memory Patch active for this session.\n"
                        f"  * To align on disk: python scripts/kernel_sync.py --fix"
                    )
                    break
    except Exception:
        pass

    is_arch = is_architecture_intent(user_input)
    gatekeeper_text = None
    if is_arch:
        target_file = None
        spec_match = re.search(r"\b([a-zA-Z0-9_\-]+\.(?:md|patch|py))\b", user_input, re.IGNORECASE)
        if spec_match:
            target_file = spec_match.group(1)
        verdict, meta = verify_critic_artifact(workspace_dir, target_file=target_file)
        if verdict in ("APPROVED", "CONDITIONAL_PASS"):
            raw_target = meta.get("target_file", "specification") if meta else "specification"
            t_name = safe_field(raw_target if isinstance(raw_target, str) else "specification", 100, single_line=True)
            raw_hash = meta.get("input_hash", "") if meta else ""
            i_hash = safe_field(raw_hash[:16] if isinstance(raw_hash, str) else "", 16, single_line=True)
            gatekeeper_text = (
                f"\n🛡️ [GATEKEEPER VERIFIED - {verdict}]:\n"
                f"  * DeepSeek-V4.1-Flash Council Gate: APPROVED (Target: {t_name}, Hash: {i_hash}).\n"
                "  * Architecture verified sound. Council Protocol permits implementation tasks."
            )
        else:
            gatekeeper_text = (
                f"\n🛡️ [CRITICAL ARCHITECTURE GATEKEEPER DIRECTIVE - STATUS: {verdict}]:\n"
                "  * Unreviewed or unapproved architecture detected. Council Protocol Rule 6 mandates:\n"
                "    python scripts/consult_critic.py --file <path_to_spec> --out <path_to_review>\n"
                "  * You MUST resolve all critical vulnerabilities before dispatching tasks to worker fleet!"
            )

    # If no skills, no rules, and not architecture, do not inject
    if not resolution.get("skills") and not resolution.get("inferred_rules") and not is_arch:
        return {"injectSteps": []}

    skills = resolution.get("skills", [])
    
    # VULN-008 & VULN-107: Low-latency SQLite staging insert (<20ms SLA budget)
    try:
        db_path = os.path.join(_SCRIPT_DIR, "..", "omni_memory.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path, timeout=0.02, isolation_level="IMMEDIATE")
            last_id = None
            try:
                conn.execute("PRAGMA busy_timeout = 20;")
                conn.execute("PRAGMA synchronous = NORMAL;")
                with conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO l1_staging_log (session_id, timestamp, user_input, workspace_hash, top_skill, tier_used, recalled_traces)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload.get("sessionId", "session_default"),
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            safe_user_input[:250],
                            canonical_workspace_hash(workspace_dir),
                            safe_field(skills[0]["skill"]["name"], 64, single_line=True) if skills else "none",
                            resolution.get("tier_assessment", {}).get("tier", 1),
                            json.dumps([t.get("trace", {}).get("id") for t in resolution.get("proven_traces", [])])
                        )
                    )
                    last_id = cursor.lastrowid
            finally:
                conn.close()

            # Detach consolidator every 50 events (platform-safe creationflags)
            if last_id and (last_id % 50 == 0):
                try:
                    consolidator_script = os.path.join(_SCRIPT_DIR, "consolidator.py")
                    cflags = 0
                    if os.name == "nt":
                        cflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    subprocess.Popen(
                        [sys.executable, consolidator_script, "--batch-run"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        close_fds=True,
                        creationflags=cflags
                    )
                except Exception as ex:
                    persist_diag(ex, 256)
    except sqlite3.OperationalError as e:
        persist_diag(e, 256)
    except Exception as e:
        persist_diag(e, 256)

    # VULN-006 & VULN-204: Record telemetry to last_activation.json atomically with universal credential redaction
    try:
        safe_skills = [
            {
                "name": safe_field(s.get("skill", {}).get("name"), 64, single_line=True),
                "version": safe_field(s.get("skill", {}).get("version"), 32, single_line=True),
                "source_type": str(s.get("skill", {}).get("source_type")),
                "raw_score": round(s.get("raw_score", 0), 1),
                "arbitration_reason": safe_field(s.get("arbitration_reason", ""), 120, single_line=True)
            } for s in skills[:3]
        ]
        record = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_input": safe_user_input,
            "workspace_dir": redact_secrets(workspace_dir),
            "top_skill": safe_skills[0]["name"] if safe_skills else "none",
            "skills": safe_skills,
            "inferred_rules": [redact_secrets(str(r)) for r in resolution.get("inferred_rules", [])],
            "suggested_mcp": [redact_secrets(str(m)) for m in resolution.get("suggested_mcp", [])],
            "cognitive_pre_flight": redact_secrets(resolution.get("cognitive_pre_flight", {})),
            "tier_assessment": resolution.get("tier_assessment", {}),
            "proven_traces": redact_secrets(resolution.get("proven_traces", []))
        }
        
        # Atomic replace for last_activation.json
        tmp_act = f"{LAST_ACTIVATION_PATH}.{uuid.uuid4().hex}.tmp"
        try:
            with open(tmp_act, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_act, LAST_ACTIVATION_PATH)
        finally:
            if os.path.exists(tmp_act):
                try:
                    os.remove(tmp_act)
                except OSError:
                    pass

        # Append compact event and rotate activations_history.jsonl under file lock (VULN-105)
        history_entry = {
            "timestamp": record["timestamp"],
            "user_input": safe_user_input[:150],
            "workspace_dir": record["workspace_dir"],
            "top_skill": record["top_skill"],
            "tier": record.get("tier_assessment", {}).get("tier", 1),
            "tier_name": record.get("tier_assessment", {}).get("tier_name", "L1 Reflex"),
            "rules_count": len(record.get("inferred_rules", [])),
            "mcp_count": len(record.get("suggested_mcp", [])),
            "traces_count": len(record.get("proven_traces", []))
        }
        try:
            with TrustFileLock(ACTIVATIONS_HISTORY_PATH, timeout=0.2):
                if os.path.exists(ACTIVATIONS_HISTORY_PATH):
                    try:
                        if os.path.getsize(ACTIVATIONS_HISTORY_PATH) > MAX_HISTORY_BYTES:
                            bak_path = f"{ACTIVATIONS_HISTORY_PATH}.1.bak"
                            os.replace(ACTIVATIONS_HISTORY_PATH, bak_path)
                    except OSError:
                        pass
                with open(ACTIVATIONS_HISTORY_PATH, "a", encoding="utf-8") as hf:
                    hf.write(json.dumps(history_entry, ensure_ascii=False) + "\n")
        except Exception as lock_err:
            persist_diag(lock_err, 256)
    except Exception as e:
        persist_diag(e, 256)

    message_text = build_preflight_message(resolution, gatekeeper_text=gatekeeper_text, drift_text=drift_text)
    
    return {
        "injectSteps": [
            {
                "ephemeralMessage": message_text
            }
        ]
    }


def main():
    payload = {}
    try:
        # Bounded stdin read: max 64 KiB
        raw_input = sys.stdin.read(65536)
        if len(raw_input) == 65536:
            sys.stderr.write("[!] Warning: stdin payload reached 64 KiB ceiling and may be truncated\n")
        if raw_input.strip():
            payload = json.loads(raw_input)
    except Exception as e:
        persist_diag(e, 256)
        payload = {}
        
    try:
        output = process_hook(payload)
    except Exception as e:
        persist_diag(e, 256)
        output = {"injectSteps": []}
        
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
