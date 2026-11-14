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
import time
import uuid
import stat
import sqlite3
import subprocess
import datetime
import hashlib
import unicodedata
from typing import Any, Optional, Dict, List, Tuple

# Ensure scripts directory is on sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from memory_utils import (
    canonical_workspace_hash,
    legacy_workspace_hash,
    find_workspace_root,
    redact_secrets,
    persist_diag,
    verify_audit_meta,
    hash_prompt,
)
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

MANDATORY_KERNEL_INVARIANTS = (
    "🛡️ [OMNI-KERNEL v4.1 MANDATORY INVARIANTS ACTIVE]:\n"
    "  * 1. Zero-Trust Security: Validate all inputs at trust boundaries. Never leak secrets.\n"
    "  * 2. Reliable Engineering: Fail loudly with context. Never swallow exceptions. Immutability first.\n"
    "  * 3. Ponytail Simplicity: Smallest complete working diff wins. YAGNI. Codebase > Stdlib > Deps.\n"
    "  * 4. Bilingual Native Parity: First-class English & Tiếng Việt reasoning and indexing."
)


def is_architecture_intent(prompt: str) -> bool:
    """Detects whether prompt involves major architectural design, RFC, or SDD specification."""
    return bool(GATEKEEPER_INTENT_PATTERN.search(prompt))


def sanitize_injected_text(val: Any, max_len: int = 250, single_line: bool = False) -> str:
    """
    Sanitizes workspace-derived content to prevent markdown/instruction injection (VULN-004, VULN-205, VULN-008, VULN-007).
    Pre-truncates input to bounded size before any regex/transformation to prevent CPU DoS on multi-megabyte payloads.
    Strips control characters, surrogates, line separators, neutralizes comment delimiters and markdown fences.
    """
    if val is None:
        return ""
    text = str(val)
    max_len = max(3, max_len)
    # Pre-truncate to bounded length before regex to prevent CPU DoS (VULN-007)
    if len(text) > max_len * 2:
        text = text[:max_len * 2]
    # Strip dangerous control characters, surrogates (U+D800..U+DFFF), and line/para separators (VULN-008)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff]", "", text)
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
    Universal workspace-derived field gatekeeper for presentation-layer text (VULN-202, VULN-001, VULN-006, VULN-007).
    Pre-truncates input, applies secret redaction, and runs AssimilatorGuard cognitive injection scanning.
    Does not blank benign descriptive words (e.g. 'curl', 'base64', URLs).
    """
    clean = sanitize_injected_text(val, max_len=max_len, single_line=single_line)
    # Redact credentials and API keys before scanning and output injection (VULN-001)
    clean = redact_secrets(clean) or ""
    # Cognitive injection / override scanning for presentation-layer text (VULN-006)
    safe, violations = AssimilatorGuard.scan_injection_only(clean)
    if not safe:
        persist_diag(f"Field blocked by security policy: {clean[:40]}... ({violations[:1]})", 128)
        return "[BLOCKED_BY_POLICY]"
    return clean


def verify_critic_artifact(workspace_dir: str, target_file: str = None, user_prompt: Optional[str] = None) -> tuple:
    """
    Decoupled non-blocking filesystem verification (<0.1ms).
    Reads candidate review files with O_NONBLOCK and S_ISREG check (VULN-203).
    Enforces HMAC-SHA256 authenticity signature (VULN-201) and canonical input_hash matching (VULN-003).
    """
    candidate_names = ["CRITIC_REVIEW.md", "AUDIT_REVIEW.md", "DEEPSEEK_REVIEW.md"]
    candidate_paths = [os.path.join(workspace_dir, name) for name in candidate_names]

    # Bounded specs and audits directory traversal (max 15 entries) to preserve SLA (VULN-203)
    try:
        specs_dir = os.path.join(workspace_dir, "specs")
        if os.path.isdir(specs_dir):
            for name in candidate_names:
                candidate_paths.append(os.path.join(specs_dir, name))
            for entry in os.listdir(specs_dir)[:15]:
                sub_path = os.path.join(specs_dir, entry)
                if os.path.isdir(sub_path):
                    for name in candidate_names:
                        candidate_paths.append(os.path.join(sub_path, name))

        audits_dir = os.path.join(workspace_dir, "docs", "audits")
        if os.path.isdir(audits_dir):
            md_entries = [e for e in os.listdir(audits_dir) if e.endswith(".md")]
            for entry in md_entries[:30]:
                candidate_paths.append(os.path.join(audits_dir, entry))
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
                audits_cand = os.path.join(workspace_dir, "docs", "audits", clean_target)
                if os.path.isfile(audits_cand):
                    target_full_path = os.path.normcase(os.path.realpath(audits_cand))
                else:
                    specs_dir = os.path.join(workspace_dir, "specs")
                    if os.path.isdir(specs_dir):
                        # Bounded traversal: max 15 entries, max depth 2 (VULN-004)
                        for entry in os.listdir(specs_dir)[:15]:
                            cand_entry = os.path.join(specs_dir, entry)
                            if os.path.isfile(cand_entry) and entry == clean_target:
                                target_full_path = os.path.normcase(os.path.realpath(cand_entry))
                                break
                            elif os.path.isdir(cand_entry):
                                sub_cand = os.path.join(cand_entry, clean_target)
                                if os.path.isfile(sub_cand):
                                    target_full_path = os.path.normcase(os.path.realpath(sub_cand))
                                    break

    best_verdict = "UNREVIEWED"
    best_meta = None

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
                header_bytes = os.read(c_fd, 8192)
                header = header_bytes.decode("utf-8", errors="ignore")
                review_mtime = c_st.st_mtime
            finally:
                os.close(c_fd)

            match = re.search(r"<!--\s*OMNI_AUDIT_META:\s*([\s\S]*?)\s*-->", header)
            if not match:
                continue

            try:
                meta = json.loads(match.group(1).strip())
            except Exception:
                continue

            # VULN-201 & VULN-003: Verify cryptographic authenticity signature via HMAC-SHA256
            # Do NOT fail closed on first candidate; continue to evaluate all candidates (prevents shadowing attack)
            if not verify_audit_meta(meta):
                continue

            # VULN-001, VULN-004 & VULN-007: Mandatory workspace binding with unified find_workspace_root & dual-hash support
            meta_ws_hash = str(meta.get("workspace_hash", "")).strip().lower()
            if not meta_ws_hash:
                continue
            ws_root = find_workspace_root(workspace_dir)
            current_ws_hash = canonical_workspace_hash(ws_root).lower()
            legacy_ws_hash = legacy_workspace_hash(ws_root).lower()
            direct_ws_hash = canonical_workspace_hash(workspace_dir).lower()
            direct_leg_hash = legacy_workspace_hash(workspace_dir).lower()
            is_committed_repo_audit = (
                os.path.basename(os.path.dirname(c_path)).lower() == "audits"
                and os.path.basename(c_path).lower().startswith("omni_kernel_")
            )
            if meta_ws_hash not in (current_ws_hash, legacy_ws_hash, direct_ws_hash, direct_leg_hash) and not is_committed_repo_audit:
                continue

            meta_target = meta.get("target_file")
            is_inline = (meta_target == "inline_prompt")

            # VULN-HR-001: When target_file is specified, reject inline_prompt bypass
            if target_file and is_inline:
                continue

            # VULN-001 & VULN-002: When target_file is absent (inline prompt), require meta.target_file == 'inline_prompt'
            # and verify meta.input_hash against the current user_prompt hash to prevent approval replay.
            if not target_file:
                if not is_inline:
                    continue
                # Fail closed: user_prompt MUST be a non-empty string (VULN-002)
                if not user_prompt or not isinstance(user_prompt, str) or not user_prompt.strip():
                    meta["stale_reason"] = "user_prompt is required for inline_prompt verification"
                    if best_verdict == "UNREVIEWED":
                        best_meta = meta
                    continue
                meta_hash = meta.get("input_hash", "")
                if not isinstance(meta_hash, str) or not meta_hash.strip():
                    meta["stale_reason"] = "input_hash missing or invalid in inline audit metadata"
                    if best_verdict == "UNREVIEWED":
                        best_verdict = "STALE_REVIEW"
                        best_meta = meta
                    continue
                calc_prompt_hash = hash_prompt(user_prompt).lower()
                calc_raw_hash = hashlib.sha256(user_prompt.encode("utf-8")).hexdigest().lower()
                expected_hash = meta_hash.replace("sha256:", "").strip().lower()
                if expected_hash not in (calc_prompt_hash, calc_raw_hash):
                    meta["stale_reason"] = "user prompt hash mismatch with inline review"
                    if best_verdict == "UNREVIEWED":
                        best_verdict = "STALE_REVIEW"
                        best_meta = meta
                    continue

            # VULN-003 & VULN-HR-003: If target_file specified, require canonical path on disk
            if target_file:
                if not target_full_path or not os.path.isfile(target_full_path):
                    meta["stale_reason"] = "target_file specified does not exist on disk (missing)"
                    if best_verdict == "UNREVIEWED":
                        best_meta = meta
                    continue

                if not meta_target or not isinstance(meta_target, str):
                    continue

                cand_meta = meta_target if os.path.isabs(meta_target) else os.path.join(workspace_dir, meta_target)
                if not os.path.exists(cand_meta):
                    cand_meta_audits = os.path.join(workspace_dir, "docs", "audits", os.path.basename(meta_target))
                    if os.path.exists(cand_meta_audits):
                        cand_meta = cand_meta_audits
                    elif os.path.basename(meta_target).lower() == os.path.basename(target_full_path).lower():
                        cand_meta = target_full_path
                    else:
                        continue
                meta_target_canonical = os.path.normcase(os.path.realpath(cand_meta))

                if meta_target_canonical != target_full_path:
                    continue

            # Anti-TOCTOU Freshness & Cryptographic Hash Validation (VULN-HR-002, VULN-104, VULN-002)
            if target_full_path:
                meta_hash = meta.get("input_hash")
                if not isinstance(meta_hash, str) or not meta_hash.strip():
                    meta["stale_reason"] = "input_hash missing or invalid in audit metadata"
                    if best_verdict == "UNREVIEWED":
                        best_verdict = "STALE_REVIEW"
                        best_meta = meta
                    continue

                # Open target once with O_RDONLY | O_NOFOLLOW | O_NONBLOCK to eliminate TOCTOU and FIFO blocking races (VULN-002)
                t_flags = os.O_RDONLY
                if hasattr(os, "O_NOFOLLOW"):
                    t_flags |= os.O_NOFOLLOW
                if hasattr(os, "O_NONBLOCK"):
                    t_flags |= os.O_NONBLOCK
                if hasattr(os, "O_BINARY"):
                    t_flags |= os.O_BINARY

                try:
                    fd = os.open(target_full_path, t_flags)
                except OSError:
                    continue

                try:
                    st = os.fstat(fd)
                    if not stat.S_ISREG(st.st_mode):
                        meta["stale_reason"] = "target_file is not a regular file (e.g. FIFO or directory)"
                        if best_verdict == "UNREVIEWED":
                            best_meta = meta
                        continue
                    if st.st_size > 5 * 1024 * 1024:
                        meta["stale_reason"] = "target_file exceeds 5 MiB size limit"
                        if best_verdict == "UNREVIEWED":
                            best_meta = meta
                        continue

                    raw_chunks = []
                    hasher = hashlib.sha256()
                    while True:
                        chunk = os.read(fd, 65536)
                        if not chunk:
                            break
                        hasher.update(chunk)
                        raw_chunks.append(chunk)
                    current_hash = hasher.hexdigest()
                    raw_data_bytes = b"".join(raw_chunks)
                    normalized_lf_hash = hashlib.sha256(raw_data_bytes.replace(b"\r\n", b"\n")).hexdigest()

                    target_mtime = st.st_mtime
                    if not is_committed_repo_audit and target_mtime > review_mtime + 1.0:
                        meta["stale_reason"] = "target_file was modified after audit review generation"
                        if best_verdict == "UNREVIEWED":
                            best_verdict = "STALE_REVIEW"
                            best_meta = meta
                        continue
                finally:
                    os.close(fd)

                expected_hash = meta_hash.replace("sha256:", "").strip().lower()
                if expected_hash not in (current_hash.lower(), normalized_lf_hash.lower()):
                    meta["stale_reason"] = "target_file content hash mismatch (modified since audit)"
                    if best_verdict == "UNREVIEWED":
                        best_verdict = "STALE_REVIEW"
                        best_meta = meta
                    continue

            verdict = meta.get("verdict", "UNREVIEWED")
            # VULN-005: Highest precedence: approved review immediately returned
            if verdict in ("APPROVED", "CONDITIONAL_PASS"):
                return verdict, meta
            if best_verdict == "UNREVIEWED":
                best_verdict = verdict
                best_meta = meta

        except Exception as e:
            persist_diag(e, 256)
            sys.stderr.write(f"[!] Warning: Exception during critic verification of {c_path}: {e}\n")
            continue

    return best_verdict, best_meta


def build_preflight_message(resolution: dict, gatekeeper_text: str = None, drift_text: str = None) -> str:
    """Formats the cognitive pre-flight resolution into a clean, sanitized markdown block (VULN-004, VULN-202)."""
    lines = ["[OMNI-KERNEL v4.3 PRE-FLIGHT ACTIVATION]"]
    
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
                mand_fields = [safe_field(m, 120, single_line=True) for m in mand]
                clean_mand = [c for c in mand_fields if c != "[BLOCKED_BY_POLICY]"]
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

    # 6. Active Cloud Worker Fleet Directives
    lines.append("\n🤖 Active Cloud Worker Fleet Directives (MANDATORY DELEGATION INVARIANT):")
    lines.append("  * gemini_worker_cloud: Google Gemini 3.5 Flash-Lite / 3.8 Flash / 4 Argon (1M context; rapid in-place edits, test synthesis, self-healing verification loops, heavy generation, multimodal vision, Argon deep reasoning)")
    lines.append("  * deepseek_worker_cloud: Independent spec & diff audit gatekeeper (deepseek_audit_spec, deepseek_audit_diff)")
    lines.append("  * DELEGATION MANDATE: Do NOT generate large code, boilerplate edits, or test suites in primary Cloud context. Delegate implementation, fast edits, test generation, and self-healing verification loops to 'gemini_worker_cloud' (gemini_heavy_code_gen, gemini_fast_edit, gemini_generate_tests, gemini_autonomous_loop, gemini_multimodal_vision, gemini_argon_solve), and run 'deepseek_worker_cloud' for critical spec/diff audits. Primary agent acts strictly as Architect & Gatekeeper.")

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

    # Injection-scanned and sanitized kernel/gatekeeper directives (VULN-001)
    if drift_text:
        clean_drift = safe_field(drift_text, 1000, single_line=False)
        if clean_drift != "[BLOCKED_BY_POLICY]":
            lines.append(clean_drift)
    if gatekeeper_text:
        clean_gate = safe_field(gatekeeper_text, 1000, single_line=False)
        if clean_gate != "[BLOCKED_BY_POLICY]":
            lines.append(clean_gate)
    return "\n".join(lines)


def process_pre_tool_use(payload: dict) -> dict:
    """Zero-friction PreToolUse Plan Gate: never blocks medium tasks and auto-unlocks on plan/doc writes or fast-bypass."""
    try:
        tool_call = payload.get("toolCall") if isinstance(payload.get("toolCall"), dict) else {}
        tool_name = str(tool_call.get("name", "")).strip()
        args = tool_call.get("args") if isinstance(tool_call.get("args"), dict) else {}

        target_path = args.get("Path") or args.get("file_path") or args.get("target_file") or ""
        target_parent = os.path.dirname(os.path.normpath(str(target_path).strip())) if str(target_path).strip() and os.path.isabs(str(target_path).strip()) else ""

        workspace_paths = payload.get("workspacePaths")
        workspace_dir = None
        if isinstance(workspace_paths, list) and workspace_paths and isinstance(workspace_paths[0], str) and workspace_paths[0].strip():
            workspace_dir = os.path.realpath(os.path.normpath(workspace_paths[0].strip()))
        elif isinstance(payload.get("workspacePath"), str) and payload["workspacePath"].strip():
            workspace_dir = os.path.realpath(os.path.normpath(payload["workspacePath"].strip()))
        elif target_parent and os.path.isdir(target_parent):
            workspace_dir = os.path.realpath(target_parent)
        elif isinstance(payload.get("cwd"), str) and payload["cwd"].strip():
            workspace_dir = os.path.realpath(os.path.normpath(payload["cwd"].strip()))
        if not workspace_dir or not os.path.isdir(workspace_dir):
            workspace_dir = os.path.realpath(os.getcwd())

        unlock_marker = os.path.join(workspace_dir, ".omni", "plan_unlocked.json")

        def _write_unlock(source: str) -> None:
            if not os.path.isdir(workspace_dir):
                return
            try:
                os.makedirs(os.path.dirname(unlock_marker), exist_ok=True)
                with open(unlock_marker, "w", encoding="utf-8") as uf:
                    json.dump({
                        "unlocked_at": time.time(),
                        "conversation_id": str(payload.get("conversationId", "")),
                        "source": source,
                    }, uf, ensure_ascii=False)
            except Exception:
                pass

        # Rule A: Auto-unlock on plan, spec, doc, scratch, or test writes
        norm_target = str(target_path).replace("\\", "/").lower()
        base_target = os.path.basename(norm_target)
        norm_with_slash = f"/{norm_target.lstrip('/')}"
        if norm_target and (
            norm_target.endswith(".md")
            or any(seg in norm_with_slash for seg in ("/.omni/", "/scratch/", "/brain/", "/specs/", "/.specify/", "/tests/"))
            or base_target.startswith("test_")
            or bool(re.search(r"(?:^|[._\-])(plan|spec|tasks|constitution)(?:$|[._\-])", base_target))
        ):
            _write_unlock(norm_target[-120:])
            return {"decision": "allow"}

        last_input = str(payload.get("lastUserInput") or payload.get("prompt") or "").strip()
        if len(last_input) > 2048:
            last_input = last_input[:1024] + " " + last_input[-1023:]
        tail_text = ""
        transcript_path = payload.get("transcriptPath")
        if isinstance(transcript_path, str) and transcript_path.strip() and os.path.isfile(transcript_path.strip()):
            try:
                t_path = transcript_path.strip()
                t_size = os.path.getsize(t_path)
                first_json_line = ""
                with open(t_path, "rb") as tf:
                    if not last_input:
                        for _ in range(5):
                            raw_ln = tf.readline(65536)
                            if not raw_ln:
                                break
                            cand_ln = raw_ln.decode("utf-8-sig", errors="replace").strip()
                            if cand_ln.startswith("{"):
                                first_json_line = cand_ln
                                break
                    if t_size > 32768:
                        tf.seek(t_size - 32768)
                    else:
                        tf.seek(0)
                    tail_text = tf.read(32768).decode("utf-8", errors="replace")
                if not last_input and first_json_line:
                    step0 = json.loads(first_json_line)
                    s0_text = ""
                    if isinstance(step0.get("content"), str) and step0["content"].strip():
                        s0_text = step0["content"].strip()
                    elif isinstance(step0.get("parts"), list):
                        s0_text = " ".join(
                            p.get("text", "")
                            for p in step0["parts"]
                            if isinstance(p, dict) and isinstance(p.get("text"), str)
                        ).strip()
                    if s0_text:
                        last_input = (
                            (s0_text[:1024] + " " + s0_text[-1023:])
                            if len(s0_text) > 2048
                            else s0_text
                        )
            except Exception:
                pass

        # Rule B: Fast-bypass keywords in user prompt (guarded against negated phrases like 'Do NOT implement')
        has_explicit_bypass = bool(
            re.search(
                r"(--no-plan|\bskip plan\b|\bbỏ qua plan\b|\blàm luôn\b|\bsửa luôn\b|\bcode luôn\b|\btriển khai luôn\b|\bproceed\b|\btiếp tục\b)",
                last_input,
                re.IGNORECASE,
            )
        )
        has_action_bypass = bool(
            re.search(r"\b(implement|execute|triển khai)\b", last_input, re.IGNORECASE)
            and not re.search(
                r"\b(?:do\s+not|don't|not|never|without|không|chưa|đừng)\s+(?:\w+\s+){0,2}(?:implement|execute|triển khai)\b",
                last_input,
                re.IGNORECASE,
            )
        )
        if has_explicit_bypass or has_action_bypass:
            _write_unlock("bypass_keyword")
            return {"decision": "allow"}

        # Rule C: Active unlock marker, recent plan file (< 7200s), SDD repo dirs, or native exit_plan_mode hand-off
        now = time.time()
        for candidate in (
            unlock_marker,
            os.path.join(workspace_dir, ".omni", "active_plan.json"),
            os.path.join(workspace_dir, "plan.md"),
        ):
            if os.path.isfile(candidate) and (now - os.path.getmtime(candidate)) < 7200:
                return {"decision": "allow"}

        if os.path.isdir(os.path.join(workspace_dir, "specs")) or os.path.isdir(os.path.join(workspace_dir, ".specify")):
            _write_unlock("sdd_workspace_present")
            return {"decision": "allow"}

        if tail_text and re.search(r'"name"\s*:\s*"exit_plan_mode"', tail_text):
            _write_unlock("exit_plan_mode")
            return {"decision": "allow"}

        # Rule D: Warn-Once Auto-Unlock — only gate score >= 95 architectural intent once, then auto-unlock for next attempt
        from dual_tier import calculate_task_complexity
        tier_info = calculate_task_complexity(last_input, workspace_dir)
        if tier_info.get("score", 0) >= 95 and is_architecture_intent(last_input) and tool_name in ("write_file", "edit_file"):
            _write_unlock("warn_once_auto_unlock")
            return {
                "decision": "deny",
                "reason": "[Omni Plan Gate - Warn Once] High-complexity architectural task detected without an active plan. Consider creating plan.md or using gemini_execute_plan; subsequent edit is now auto-unlocked."
            }
        return {"decision": "allow"}
    except Exception:
        return {"decision": "allow"}


def process_hook(payload: dict) -> dict:
    """Core hook processing logic with robust type coercion and schema validation (VULN-006)."""
    if payload.get("hookEventName") == "PreToolUse" or "toolCall" in payload:
        return process_pre_tool_use(payload)
    raw_input_obj = payload.get("lastUserInput") if payload.get("lastUserInput") is not None else (
        payload.get("prompt") if payload.get("prompt") is not None else payload.get("userInput")
    )
    if raw_input_obj is None:
        return {"injectSteps": []}
    if isinstance(raw_input_obj, (dict, list)):
        raw_user_input = json.dumps(raw_input_obj, ensure_ascii=False).strip()
    else:
        raw_user_input = str(raw_input_obj).strip()
    
    # Skip empty input or slash commands
    if not raw_user_input:
        return {"injectSteps": []}
    if raw_user_input.startswith("/") and not raw_user_input.startswith("/teamwork"):
        return {"injectSteps": []}
    
    # T011: Full-sentence boundary matching for filler suppression (<1.0ms fast-exit)
    if FILLER_PATTERN.match(raw_user_input) or len(raw_user_input.strip("!.?, \t\n\r")) <= 2:
        return {"injectSteps": []}

    # Redact sensitive credentials first before any truncation to prevent splitting secrets across boundaries (VULN-005)
    safe_full_input = str(redact_secrets(raw_user_input) or raw_user_input)
    # T010: 2,048-char head clamping invariant
    safe_user_input = safe_full_input[:2048]
    user_input = safe_user_input
    
    # Extract workspace paths with strict schema validation (VULN-004)
    workspace_paths = payload.get("workspacePaths")
    workspace_dir = None
    if isinstance(workspace_paths, list) and workspace_paths and isinstance(workspace_paths[0], str) and workspace_paths[0].strip():
        workspace_dir = os.path.realpath(os.path.normpath(workspace_paths[0].strip()))
    elif isinstance(payload.get("workspacePath"), str) and payload["workspacePath"].strip():
        workspace_dir = os.path.realpath(os.path.normpath(payload["workspacePath"].strip()))
    if not workspace_dir or not os.path.exists(workspace_dir):
        workspace_dir = os.path.realpath(os.getcwd())
    
    try:
        from resolver import resolve_skill
        # Pass safe_user_input (credentials redacted) to eliminate secret leakage in resolver logs (VULN-003)
        resolution = resolve_skill(intent_text=safe_user_input, workspace_dir=workspace_dir, unified=True)
    except Exception as e:
        persist_diag(redact_secrets(str(e)), 256)
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
        spec_match = re.search(
            r"\b((?:spec|plan|constitution|tasks|checklist|rfc[a-zA-Z0-9_\-]*|frc[a-zA-Z0-9_\-]*|omni_kernel_[a-zA-Z0-9_\-]*)\.(?:md|patch))\b",
            user_input,
            re.IGNORECASE,
        )
        if spec_match:
            target_file = spec_match.group(1)
        verdict, meta = verify_critic_artifact(workspace_dir, target_file=target_file, user_prompt=raw_user_input)
        if verdict in ("APPROVED", "CONDITIONAL_PASS"):
            raw_target = meta.get("target_file", "specification") if meta else "specification"
            t_name = os.path.basename(str(raw_target))[:64]
            raw_hash = meta.get("input_hash", "") if meta else ""
            i_hash = str(raw_hash)[:16]
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
    
    # VULN-002 & Principle I (<25ms SLA): Fast non-blocking append to L1 staging spool (0ms SQLite WAL checkpoint overhead).
    # Background consolidator.py drains l1_staging_spool.jsonl into omni_memory.db l1_staging_log out-of-band.
    try:
        spool_path = os.path.join(_SCRIPT_DIR, "l1_staging_spool.jsonl")
        spool_lock = spool_path + ".lock"
        spool_entry = {
            "session_id": redact_secrets(str(payload.get("sessionId", "session_default")))[:64],
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "user_input": safe_user_input[:250],
            "workspace_hash": canonical_workspace_hash(workspace_dir),
            "top_skill": safe_field(skills[0]["skill"]["name"], 64, single_line=True) if skills else "none",
            "tier_used": resolution.get("tier_assessment", {}).get("tier", 1),
            "recalled_traces": [t.get("trace", {}).get("id") for t in resolution.get("proven_traces", [])]
        }
        should_spawn_consolidator = False
        with TrustFileLock(spool_lock, timeout=0.05):
            if os.path.exists(spool_path):
                try:
                    sz = os.path.getsize(spool_path)
                    if sz > 10 * 1024 * 1024:
                        os.replace(spool_path, spool_path + ".1.bak")
                    elif sz > 25 * 1024:
                        should_spawn_consolidator = True
                except Exception:
                    pass
            with open(spool_path, "a", encoding="utf-8") as sf:
                sf.write(json.dumps(spool_entry, ensure_ascii=False) + "\n")

        if should_spawn_consolidator:
            try:
                consolidator_script = os.path.join(_SCRIPT_DIR, "consolidator.py")
                cflags = 0
                if os.name == "nt":
                    cflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                subprocess.Popen(
                    [sys.executable, consolidator_script, "--batch-run", "--workspace", workspace_dir],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    creationflags=cflags
                )
            except Exception as ex:
                persist_diag(ex, 256)
    except Exception as e:
        persist_diag(e, 256)

    # VULN-006, VULN-204 & VULN-008: Record telemetry to last_activation.json atomically with universal credential redaction
    try:
        safe_skills = [
            {
                "name": safe_field(s.get("skill", {}).get("name"), 64, single_line=True),
                "version": safe_field(s.get("skill", {}).get("version"), 32, single_line=True),
                "source_type": safe_field(str(s.get("skill", {}).get("source_type")), 32, single_line=True),
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
            "tier_assessment": redact_secrets(resolution.get("tier_assessment", {})),
            "proven_traces": redact_secrets(resolution.get("proven_traces", []))
        }
        
        # Atomic replace for last_activation.json (no blocking fsync on telemetry to preserve <25ms SLA)
        tmp_act = f"{LAST_ACTIVATION_PATH}.{uuid.uuid4().hex}.tmp"
        try:
            with open(tmp_act, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
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
            with TrustFileLock(ACTIVATIONS_HISTORY_PATH, timeout=0.02):
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
        # Bounded stdin read: read up to 262145 bytes (256 KiB + 1 byte) to detect truncation accurately
        if hasattr(sys.stdin, "buffer"):
            raw_bytes = sys.stdin.buffer.read(262145)
        else:
            raw_bytes = sys.stdin.read(262145).encode("utf-8")
        if len(raw_bytes) > 262144:
            sys.stderr.write("[!] Warning: stdin payload exceeded 256 KiB ceiling and was truncated\n")
            output = {
                "injectSteps": [
                    {
                        "ephemeralMessage": f"⚠️ [OMNI-KERNEL WARNING]: Pre-flight input exceeded 256 KiB transport ceiling. Enforcing baseline security directives:\n\n{MANDATORY_KERNEL_INVARIANTS}"
                    }
                ]
            }
            print(json.dumps(output, ensure_ascii=True))
            return
        raw_input = raw_bytes.decode("utf-8", errors="replace")
        if raw_input.strip():
            payload = json.loads(raw_input)
    except json.JSONDecodeError as e:
        persist_diag(e, 256)
        output = {
            "injectSteps": [
                {
                    "ephemeralMessage": f"⚠️ [OMNI-KERNEL WARNING]: Pre-flight hook payload malformed JSON ({type(e).__name__}). Enforcing baseline security directives:\n\n{MANDATORY_KERNEL_INVARIANTS}"
                }
            ]
        }
        print(json.dumps(output, ensure_ascii=True))
        return
    except Exception as e:
        persist_diag(e, 256)
        payload = {}
        
    try:
        output = process_hook(payload)
    except Exception as e:
        persist_diag(e, 256)
        output = {"injectSteps": []}
        
    # VULN-008: ensure_ascii=True guarantees safe stdout encoding across all platforms and surrogates
    print(json.dumps(output, ensure_ascii=True))


if __name__ == "__main__":
    main()
