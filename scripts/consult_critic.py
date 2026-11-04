#!/usr/bin/env python3
"""
Omni-Auditor Strict Architecture Gatekeeper Client (DeepSeek-V4.1-Flash).
Part of Omni-Kernel v4.1 Council Protocol.

100% Python Standard Library (zero external dependencies).
Provides direct CLI parity, Devil's Advocate red-teaming audits, monotonic deadline clamping,
jittered exponential backoff, and cryptographic target-file binding.

Usage:
    python scripts/consult_critic.py --file RFC_DRAFT.md --out AUDIT_REVIEW.md
    python scripts/consult_critic.py --prompt "Đánh giá kiến trúc này..." --mode rfc
    python scripts/consult_critic.py --file diff.patch --mode code --strict
"""

import argparse
import datetime
import hashlib
import json
import os
import random
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure scripts directory is in sys.path for sanitizer import
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from sanitizer import redact_credentials
except ImportError:
    # Graceful fallback if sanitizer cannot be imported
    def redact_credentials(text: Optional[str]) -> str:
        return text or ""

# Exit code constants (Standardized POSIX / Omni-Kernel contract)
EXIT_APPROVED = 0              # Approved or Conditional Pass (non-strict)
EXIT_CRITIQUE_GENERATED = 1    # Rejected / Changes Requested / Critique with findings
EXIT_AUTH_QUOTA = 2            # Auth failure, Quota exhaustion, Rate limit retry exhaustion
EXIT_TIMEOUT_NETWORK = 3       # Monotonic deadline exhausted, network disconnect, 5xx outage
EXIT_CONFIG_USAGE = 4          # CLI usage error, argument parsing, file traversal / not found
EXIT_SYSTEM_STRICT = 5         # Schema failure, internal system fault, or strict mode rejection

# Protocol constants
DEFAULT_TIMEOUT = 30.0
MIN_TIMEOUT = 10.0             # Must be > MIN_INFER_WINDOW (8.0s) to allow at least one viable inference attempt
MAX_TIMEOUT = 300.0
MIN_INFER_WINDOW = 8.0         # FLAW-004: Minimum viable inference window for DeepSeek (seconds)
MAX_FILE_SIZE = 4.5 * 1024 * 1024  # 4.5 MB context ceiling
DEFAULT_API_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")


class StrictArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser subclass enforcing strict POSIX exit code 4 on usage / argument errors.
    Prevents collision with exit code 2 (reserved for Authentication / Quota failures).
    """
    def error(self, message: str) -> None:
        sys.stderr.write(f"[!] LỖI THAM SỐ (CLI Error): {message}\n")
        self.print_usage(sys.stderr)
        sys.exit(EXIT_CONFIG_USAGE)


def load_api_key(api_key_override: Optional[str] = None) -> str:
    """
    Loads DeepSeek API Key from environment or local .env file.
    Enforces zero-hardcoding and fails fast with exit code 2 if missing.
    """
    if api_key_override and api_key_override.strip():
        return api_key_override.strip()

    # 1. Environment variable
    env_key = os.environ.get("DEEPSEEK_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    # 2. Search .env in current and parent directories
    search_dir = os.path.abspath(os.getcwd())
    for _ in range(5):
        candidate_env = os.path.join(search_dir, ".env")
        if os.path.isfile(candidate_env):
            try:
                with open(candidate_env, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or not line:
                            continue
                        match = re.match(r"^DEEPSEEK_API_KEY\s*=\s*(.*)$", line, re.IGNORECASE)
                        if match:
                            raw_val = match.group(1).strip().strip("'\"")
                            if raw_val:
                                return raw_val
            except Exception:
                pass
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            break
        search_dir = parent

    sys.stderr.write(
        "[!] LỖI XÁC THỰC: DEEPSEEK_API_KEY không hợp lệ hoặc chưa được thiết lập trong biến môi trường hoặc .env!\n"
        "    Vui lòng thiết lập: set DEEPSEEK_API_KEY=your_key hoặc thêm vào file .env\n"
    )
    sys.exit(EXIT_AUTH_QUOTA)


def validate_path(raw_path: str, allowed_root: Optional[str] = None) -> str:
    """
    Validates, canonicalizes, and verifies that input file exists, is within bounds,
    and defends against directory traversal. Fails with exit code 4 on any violation.
    """
    if not raw_path or not raw_path.strip():
        sys.stderr.write("[!] LỖI THAM SỐ: Đường dẫn file rỗng!\n")
        sys.exit(EXIT_CONFIG_USAGE)

    clean_path = raw_path.strip()
    real_path = os.path.realpath(os.path.normpath(clean_path))
    real_norm = os.path.normcase(real_path)

    if allowed_root:
        root_real = os.path.realpath(os.path.normpath(allowed_root))
        root_norm = os.path.normcase(root_real)
        try:
            common = os.path.commonpath([real_norm, root_norm])
            if common != root_norm:
                sys.stderr.write(
                    f"[!] LỖI BẢO MẬT: Đường dẫn '{clean_path}' nằm ngoài thư mục cho phép '{allowed_root}'!\n"
                )
                sys.exit(EXIT_CONFIG_USAGE)
        except ValueError:
            sys.stderr.write(
                f"[!] LỖI BẢO MẬT: Khác ổ đĩa hoặc đường dẫn không hợp lệ: '{clean_path}'!\n"
            )
            sys.exit(EXIT_CONFIG_USAGE)

    if not os.path.exists(real_path):
        sys.stderr.write(f"[!] LỖI FILE: Không tìm thấy file: '{clean_path}'!\n")
        sys.exit(EXIT_CONFIG_USAGE)

    if os.path.isdir(real_path):
        sys.stderr.write(f"[!] LỖI FILE: Đường dẫn '{clean_path}' là thư mục, không phải file!\n")
        sys.exit(EXIT_CONFIG_USAGE)

    try:
        file_size = os.path.getsize(real_path)
    except OSError as e:
        sys.stderr.write(f"[!] LỖI FILE: Không thể đọc kích thước file '{clean_path}': {e}\n")
        sys.exit(EXIT_CONFIG_USAGE)

    if file_size == 0:
        sys.stderr.write(f"[!] LỖI FILE: File '{clean_path}' rỗng (0 bytes)!\n")
        sys.exit(EXIT_CONFIG_USAGE)

    if file_size > MAX_FILE_SIZE:
        sys.stderr.write(
            f"[!] LỖI FILE: Kích thước file '{clean_path}' ({file_size} bytes) vượt quá giới hạn 4.5 MB!\n"
        )
        sys.exit(EXIT_CONFIG_USAGE)

    return real_path


def build_system_prompt(mode: str) -> str:
    """
    Constructs the Devil's Advocate red-teaming system prompt with strict conditional
    vulnerability floor and edge cases contract (FLAW-001).
    """
    if mode == "code":
        return (
            "You are the Omni-Kernel Code Security & Reliability Auditor, powered by DeepSeek-V4.1-Flash.\n"
            "Your mandate is strictly RED-TEAMING code diffs and implementations before merging.\n\n"
            "PROJECT CONTEXT & EVALUATION FOCUS:\n"
            "1. SINGLE-DEVELOPER PERSONAL ENVIRONMENT: This is a personal CLI developer tool & agent harness.\n"
            "   Do NOT demand multi-tenant enterprise isolation, separate OS user accounts, or hardware TPM modules for local scripts.\n"
            "2. PRIMARY OPERATIONAL AXES:\n"
            "   - Operational Reliability: No hung processes, clean stale lockfile recovery, deadlock prevention, no unhandled crashes.\n"
            "   - Reliable Error Handling: Fail loudly with diagnostic context; never silently swallow unexpected exceptions with bare 'except: pass'.\n"
            "   - Efficiency & Performance: Low latency (<25ms pre-flight hook turnaround, sub-millisecond regex, fast cache lookups, WAL concurrency).\n"
            "   - Functional Completeness: Clean API contracts, correct parameter parsing, proper Unicode handling, no unvalidated trust boundaries.\n"
            "   - Ponytail Simplicity: Smallest complete working diff, zero unrequested abstractions or bloat.\n\n"
            "3. CONDITIONAL VULNERABILITY FLOOR:\n"
            "   - If audit findings identify operational bugs, race conditions, memory leaks, unparameterized SQL, or silent exception swallowing, "
            "you MUST issue verdict REJECTED or CONDITIONAL_PASS, and you MUST populate AT LEAST 3 distinct items in `critical_vulnerabilities` (minItems: 3).\n"
            "   - You are strictly FORBIDDEN from issuing verdict APPROVED with 0 critical vulnerabilities unless the code is verified 100% sound "
            "AND you prove AT LEAST 3 rigorous defensive failure scenarios with concrete mitigations in `edge_cases` (minItems: 3).\n\n"
            "4. RESPONSE SCHEMA (JSON object):\n"
            "{\n"
            '  "verdict": "APPROVED" | "CONDITIONAL_PASS" | "REJECTED",\n'
            '  "confidence_score": float (0.0 to 1.0),\n'
            '  "summary": "Brief executive summary in Vietnamese or English",\n'
            '  "critical_vulnerabilities": [\n'
            '    {"id": "VULN-001", "severity": "CRITICAL"|"HIGH"|"MEDIUM", "title": "...", "description": "...", "remediation": "..."}\n'
            '  ],\n'
            '  "concurrency_hazards": [\n'
            '    {"resource": "...", "hazard_type": "...", "mitigation": "..."}\n'
            '  ],\n'
            '  "edge_cases": [\n'
            '    {"scenario": "...", "consequence": "...", "mitigation": "..."}\n'
            '  ],\n'
            '  "prescriptive_directives": ["..."]\n'
            "}"
        )

    # Default: Mode RFC (Architectural Specification Review)
    return (
        "You are the Omni-Kernel Architecture Gatekeeper & Devil's Advocate, powered by DeepSeek-V4.1-Flash.\n"
        "Your mandate is strictly RED-TEAMING technical specifications, architecture RFCs, and SDD bundles.\n\n"
        "OPERATIONAL INVARIANTS & CONDITIONAL CRITIQUE CONTRACT:\n"
        "1. ZERO SYCOPHANCY: Praise, flattery, compliments, or polite fillers are STRICTLY PROHIBITED. Do not say 'Great job' or 'Looks solid'.\n"
        "2. CONDITIONAL VULNERABILITY FLOOR (FLAW-001):\n"
        "   - DeepSeek JSON mode (`response_format: {'type': 'json_object'}`) does not perform server-side Draft-07 schema validation. "
        "You MUST strictly adhere to this semantic contract:\n"
        "   - If audit findings identify architectural defects, missing error bounds, or invariant violations, "
        "you MUST issue verdict REJECTED or CONDITIONAL_PASS, and you MUST populate AT LEAST 3 distinct critical vulnerabilities in `critical_vulnerabilities` (minItems: 3).\n"
        "   - You are strictly FORBIDDEN from issuing verdict APPROVED with 0 critical vulnerabilities unless the architecture is verified 100% sound "
        "AND you document AT LEAST 3 rigorous defensive failure scenarios with concrete mitigations in `edge_cases` (minItems: 3). "
        "Issuing APPROVED with fewer than 3 edge cases is strictly invalid and will trigger automated gate rejection.\n"
        "3. CONSTITUTIONAL VERIFICATION: Audit strictly against the Omni-Kernel v4.1 Constitution (.specify/constitution.md):\n"
        "   - Principle I: Sub-millisecond L1 reflex (<0.30ms reflex, <25ms subprocess turnaround, 2,048-char head clamping, two-process boundary).\n"
        "   - Principle II: Zero-Trust Security (parameterized SQL ? only, automated regex credential redaction, local-only storage boundary).\n"
        "   - Principle III: Dual-language parity (Vietnamese & English native parity, intfloat/multilingual-e5-small model mandate).\n"
        "   - Principle IV: Physical hardware bounds (AMD Instinct MI50 VRAM Headroom strictly >3,741 MB, prompt cap <=16k tokens, llama_autostart.lock with 30s stale recovery).\n"
        "   - Principle V: Mathematically bounded consolidation (RRF k=20, Ebbinghaus stability decay S(t) in [0, 1], soft-archiving, permanent invariants).\n\n"
        "4. RESPONSE SCHEMA (JSON object):\n"
        "{\n"
        '  "verdict": "APPROVED" | "CONDITIONAL_PASS" | "REJECTED",\n'
        '  "confidence_score": float (0.0 to 1.0),\n'
        '  "summary": "Concise executive critique in Vietnamese or English",\n'
        '  "critical_vulnerabilities": [\n'
        '    {"id": "VULN-001", "severity": "CRITICAL"|"HIGH"|"MEDIUM", "title": "...", "description": "...", "remediation": "..."}\n'
        '  ],\n'
        '  "concurrency_hazards": [\n'
        '    {"resource": "...", "hazard_type": "...", "mitigation": "..."}\n'
        '  ],\n'
        '  "edge_cases": [\n'
        '    {"scenario": "...", "consequence": "...", "mitigation": "..."}\n'
        '  ],\n'
        '  "prescriptive_directives": ["..."]\n'
        "}"
    )


def calculate_sleep_duration(
    attempt: int,
    retry_after: Optional[float] = None,
    deadline: Optional[float] = None,
    min_infer_window: float = MIN_INFER_WINDOW
) -> float:
    """
    Computes jittered exponential backoff: T_wait = min(10.0, 1.0 * 2^attempt) + uniform(0.1, 0.5).
    Safely respects Retry-After header and clamps against remaining monotonic deadline budget.
    """
    base_backoff = min(10.0, 1.0 * (2 ** attempt))
    jitter = random.uniform(0.1, 0.5)
    sleep_time = base_backoff + jitter

    if retry_after is not None and retry_after > 0:
        sleep_time = max(sleep_time, min(retry_after, 10.0))

    if deadline is not None:
        remaining = deadline - time.monotonic()
        max_allowable_sleep = max(0.0, remaining - min_infer_window)
        sleep_time = min(sleep_time, max_allowable_sleep)

    return max(0.0, sleep_time)


def repair_json_string(s: str) -> Tuple[str, bool]:
    """
    Single-pass scanner to repair unescaped quotes, invalid backslashes, and raw newlines
    inside JSON string values without corrupting valid escapes or delimiters (VULN-009).
    """
    result = []
    in_string = False
    length = len(s)
    i = 0
    repaired = False
    valid_escapes = {'"', '\\', '/', 'b', 'f', 'n', 'r', 't'}

    while i < length:
        c = s[i]
        if not in_string:
            result.append(c)
            if c == '"':
                in_string = True
            i += 1
            continue

        # Inside string literal
        if c == '\\':
            if i + 1 < length:
                nxt = s[i + 1]
                if nxt in valid_escapes:
                    result.append(c)
                    result.append(nxt)
                    i += 2
                    continue
                elif nxt == 'u' and i + 5 < length and all(h in "0123456789abcdefABCDEF" for h in s[i + 2:i + 6]):
                    result.append(s[i:i + 6])
                    i += 6
                    continue
            # Invalid backslash escape -> escape it as \\
            result.append('\\\\')
            repaired = True
            i += 1
            continue

        if c == '"':
            j = i + 1
            while j < length and s[j] in " \t\r\n":
                j += 1
            next_char = s[j] if j < length else ""
            if next_char in {",", "}", "]", ":"}:
                in_string = False
                result.append(c)
            else:
                result.append('\\"')
                repaired = True
            i += 1
            continue

        if c == '\n':
            result.append('\\n')
            repaired = True
            i += 1
            continue
        if c == '\r':
            result.append('\\r')
            repaired = True
            i += 1
            continue
        if c == '\t':
            result.append('\\t')
            repaired = True
            i += 1
            continue

        result.append(c)
        i += 1

    return "".join(result), repaired


def repair_unescaped_json_quotes(s: str) -> str:
    """Backward compatibility wrapper."""
    rep, _ = repair_json_string(s)
    return rep


def extract_first_json_object(raw_str: str) -> str:
    """
    Extracts the first valid balanced JSON object string from raw_str.
    Strips markdown code fences and handles trailing non-JSON content.
    """
    s = raw_str.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s)
        s = s.strip()

    start_idx = s.find('{')
    if start_idx == -1:
        return s

    in_string = False
    escape = False
    depth = 0
    end_idx = -1
    for i in range(start_idx, len(s)):
        char = s[i]
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
    if end_idx != -1:
        return s[start_idx:end_idx]
    return s[start_idx:]


def validate_audit_verdict(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Enforces Draft-07 semantic schema validation for the DeepSeek audit verdict.
    Adheres to FLAW-001 conditional contract:
      - If verdict != 'APPROVED', critical_vulnerabilities must have >= 3 items.
      - If verdict == 'APPROVED', critical_vulnerabilities must have 0 items AND edge_cases must have >= 3 items.
    """
    if not isinstance(data, dict):
        return False, f"Audit verdict payload must be a dict, got {type(data).__name__}."

    verdict = data.get("verdict")
    if verdict not in ("APPROVED", "CONDITIONAL_PASS", "REJECTED"):
        return False, f"Invalid verdict value: '{verdict}'. Must be APPROVED, CONDITIONAL_PASS, or REJECTED."

    confidence = data.get("confidence_score")
    if confidence is not None and not isinstance(confidence, (int, float)):
        return False, f"Field 'confidence_score' must be a numeric float/int, got {type(confidence).__name__}."

    vulns = data.get("critical_vulnerabilities")
    if not isinstance(vulns, list):
        return False, "Field 'critical_vulnerabilities' must be a list."
    for idx, v in enumerate(vulns):
        if not isinstance(v, dict):
            return False, f"Item {idx} in 'critical_vulnerabilities' must be a dict, got {type(v).__name__}."

    edge_cases = data.get("edge_cases")
    if not isinstance(edge_cases, list):
        return False, "Field 'edge_cases' must be a list."
    for idx, ec in enumerate(edge_cases):
        if not isinstance(ec, dict):
            return False, f"Item {idx} in 'edge_cases' must be a dict, got {type(ec).__name__}."

    concurrency = data.get("concurrency_hazards")
    if concurrency is not None and not isinstance(concurrency, list):
        return False, "Field 'concurrency_hazards' must be a list."
    if isinstance(concurrency, list):
        for idx, ch in enumerate(concurrency):
            if not isinstance(ch, dict):
                return False, f"Item {idx} in 'concurrency_hazards' must be a dict, got {type(ch).__name__}."

    directives = data.get("prescriptive_directives")
    if directives is not None and not isinstance(directives, list):
        return False, "Field 'prescriptive_directives' must be a list."

    if verdict != "APPROVED":
        if len(vulns) < 3:
            return False, f"Verdict '{verdict}' violates conditional floor: expected >= 3 critical_vulnerabilities, got {len(vulns)}."
    else:
        if len(vulns) > 0:
            return False, f"Verdict 'APPROVED' is invalid when critical_vulnerabilities > 0 (found {len(vulns)})."
        if len(edge_cases) < 3:
            return False, f"Verdict 'APPROVED' violates proof of defense contract: expected >= 3 edge_cases, got {len(edge_cases)}."

    return True, "Valid"


def find_workspace_root(start_path: str) -> str:
    """Finds repository or workspace root walking upwards looking for .git or GEMINI.md (VULN-007)."""
    curr = os.path.realpath(os.path.normpath(start_path))
    if os.path.isfile(curr):
        curr = os.path.dirname(curr)
    while True:
        if os.path.exists(os.path.join(curr, ".git")) or os.path.exists(os.path.join(curr, "GEMINI.md")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return os.path.realpath(os.getcwd())


def format_markdown_report(
    data: Dict[str, Any],
    target_file: str,
    input_hash: str,
    model: str,
    workspace_dir: Optional[str] = None
) -> str:
    """
    Formats the JSON critique into a structured Markdown document with the cryptographic
    line 1 metadata comment (FLAW-002 Anti-Collision Header).
    """
    verdict = data.get("verdict", "REJECTED")
    raw_confidence = data.get("confidence_score", 0.0)
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    summary = data.get("summary", "No summary provided.")
    vulns = data.get("critical_vulnerabilities") if isinstance(data.get("critical_vulnerabilities"), list) else []
    concurrency = data.get("concurrency_hazards") if isinstance(data.get("concurrency_hazards"), list) else []
    edge_cases = data.get("edge_cases") if isinstance(data.get("edge_cases"), list) else []
    directives = data.get("prescriptive_directives") if isinstance(data.get("prescriptive_directives"), list) else []
    timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Cryptographic line 1 metadata header for verify_critic_artifact (<0.1ms parse)
    if target_file:
        if any(c in str(target_file) for c in ("\r", "\n", "\0")) or "-->" in str(target_file):
            raise ValueError(f"Malicious or invalid characters in target_file: {target_file!r}")
    from memory_utils import sign_audit_meta, canonical_workspace_hash
    ws_target = workspace_dir or os.getcwd()
    meta = {
        "verdict": verdict,
        "target_file": target_file,
        "input_hash": input_hash,
        "model": model,
        "hash_domain": "redacted_prompt_v1",
        "hash_algo": "sha256-v2",
        "timestamp_utc": timestamp_utc,
        "workspace_hash": canonical_workspace_hash(ws_target)
    }
    try:
        meta["signature"] = sign_audit_meta(meta)
    except Exception as e:
        sys.stderr.write(f"[!] LỖI CHỮ KÝ: Không thể tạo chữ ký HMAC cho audit metadata: {e}\n")
        raise RuntimeError(f"Audit metadata signing failed: {e}")
    meta_comment = f"<!-- OMNI_AUDIT_META: {json.dumps(meta, separators=(',', ':'))} -->\n"

    lines = [
        meta_comment,
        f"# 🛡️ Architectural Red-Teaming Audit: {target_file}",
        f"**Audit Status**: `{verdict}` | **Model**: `{model}` | **Confidence**: `{confidence:.2f}` | **Timestamp**: `{timestamp_utc}`\n",
        f"## Executive Summary\n{summary}\n",
        "## 1. Constitutional & Ring 0 Invariants Verification"
    ]

    if verdict == "APPROVED":
        lines.append("- ✅ Ring 0 Security (Zero-Trust SQL & Credential Redaction): PASS")
        lines.append("- ✅ Principle I Reflex Latency Boundary: PASS")
        lines.append("- ✅ Concurrency & Physical Resource Bounds: PASS\n")
    else:
        lines.append(f"- ⚠️ Gatekeeper Finding: Invariant check issued verdict `{verdict}` with {len(vulns)} vulnerability findings.\n")

    lines.append(f"## 2. Top Critical Architectural Vulnerabilities ({len(vulns)} identified)")
    if vulns:
        for idx, v in enumerate(vulns, 1):
            if isinstance(v, dict):
                v_id = v.get("id", f"VULN-{idx:03d}")
                sev = v.get("severity", "HIGH")
                title = v.get("title", "Untitled Vulnerability")
                desc = v.get("description", "No description.")
                rem = v.get("remediation", "No remediation specified.")
            else:
                v_id = f"VULN-{idx:03d}"
                sev = "HIGH"
                title = str(v)
                desc = str(v)
                rem = "No remediation specified."
            lines.append(f"### {idx}. [{sev}] {v_id}: {title}")
            lines.append(f"**Description**: {desc}")
            lines.append(f"**Remediation**: `{rem}`\n")
    else:
        lines.append("_No critical vulnerabilities identified. (Zero-defect floor verified)_\n")

    lines.append(f"## 3. Concurrency, Race Condition & Mutex Hazards ({len(concurrency)} identified)")
    if concurrency:
        for c in concurrency:
            if isinstance(c, dict):
                res = c.get("resource", "Unknown")
                hz = c.get("hazard_type", "Race Condition")
                mit = c.get("mitigation", "N/A")
            else:
                res = "Unknown"
                hz = "Race Condition"
                mit = str(c)
            lines.append(f"- **Resource**: `{res}` | **Hazard**: {hz} | **Mitigation**: {mit}")
        lines.append("")
    else:
        lines.append("_No concurrency or locking hazards identified._\n")

    lines.append(f"## 4. Defensive Failure Scenarios & Edge Cases ({len(edge_cases)} verified)")
    if edge_cases:
        for idx, ec in enumerate(edge_cases, 1):
            if isinstance(ec, dict):
                scen = ec.get("scenario", f"Scenario {idx}")
                conseq = ec.get("consequence", "Consequence")
                mit = ec.get("mitigation", "Mitigation")
            else:
                scen = f"Scenario {idx}"
                conseq = str(ec)
                mit = "N/A"
            lines.append(f"### {idx}. {scen}")
            lines.append(f"- **Consequence**: {conseq}")
            lines.append(f"- **Mitigation**: {mit}\n")
    else:
        lines.append("_No edge cases provided._\n")

    lines.append(f"## 5. Prescriptive Remediation Directives ({len(directives)} items)")
    if directives:
        for d in directives:
            lines.append(f"- {d}")
        lines.append("")
    else:
        lines.append("_No prescriptive directives required._\n")

    lines.append(f"## 6. Council Gate Final Verdict: `{verdict}`\n")
    return "\n".join(lines)


def execute_critic_request(
    api_key: str,
    api_base: str,
    model: str,
    system_prompt: str,
    user_content: str,
    temperature: float,
    timeout_budget: float
) -> Tuple[Dict[str, Any], str]:
    """
    Executes DeepSeek REST request with monotonic deadline clamping, dynamic socket timeout,
    and fail-fast retry abort when remaining budget < 8.0s (FLAW-004).
    """
    deadline = time.monotonic() + timeout_budget
    current_model = model
    model_fallback_attempted = False
    endpoint_url = f"{api_base.rstrip('/')}/v1/chat/completions"

    # Set process recursion guard
    os.environ["OMNI_GATEKEEPER_ACTIVE"] = "1"

    ssl_context = ssl.create_default_context()

    for attempt in range(4):  # attempt 0 + up to 3 retries
        now = time.monotonic()
        remaining_budget = deadline - now

        if remaining_budget <= 0.5:
            sys.stderr.write(
                f"[!] HẾT THỜI GIAN (Timeout): Đã vượt quá ngân sách {timeout_budget:.1f}s trước khi gửi request!\n"
            )
            sys.exit(EXIT_TIMEOUT_NETWORK)

        socket_timeout = min(180.0, max(0.1, remaining_budget))

        payload = {
            "model": current_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }
        if "flash" in current_model.lower():
            payload["reasoning_effort"] = "high"
            payload["thinking"] = {"type": "enabled"}

        payload_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint_url,
            data=payload_bytes,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Omni-Auditor-v4.1/DeepSeek-Flash (+https://antigravity.kernel)"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=socket_timeout, context=ssl_context) as resp:
                resp_bytes = resp.read()
                raw_json = json.loads(resp_bytes.decode("utf-8"))

                # Extract assistant content
                choices = raw_json.get("choices", [])
                if not choices:
                    sys.stderr.write("[!] LỖI API: DeepSeek trả về choices rỗng!\n")
                    sys.exit(EXIT_SYSTEM_STRICT)

                message = choices[0].get("message") or {}
                content_str = message.get("content")
                if not isinstance(content_str, str) or not content_str.strip():
                    sys.stderr.write("[!] LỖI MODEL: message content rỗng hoặc không phải chuỗi!\n")
                    sys.exit(EXIT_SYSTEM_STRICT)

                cleaned_json_str = extract_first_json_object(content_str)
                # Attempt direct parse first
                try:
                    parsed_verdict = json.loads(cleaned_json_str, strict=False)
                except json.JSONDecodeError:
                    # Single-pass safe repair for quotes, backslashes, and control chars (VULN-009)
                    repaired_str, was_repaired = repair_json_string(cleaned_json_str)
                    if was_repaired:
                        sys.stderr.write("[!] Warning: consult_critic applied single-pass JSON escape/quote repair\n")
                    try:
                        parsed_verdict = json.loads(repaired_str, strict=False)
                    except json.JSONDecodeError as jde:
                        # Handle failure without dumping unredacted raw content (VULN-007)
                        if os.environ.get('CRITIC_DEBUG') == '1':
                            import tempfile
                            from memory_utils import redact_secrets
                            with tempfile.NamedTemporaryFile(
                                mode='w',
                                delete=False,
                                encoding='utf-8',
                                prefix='critic_debug_',
                                suffix='.txt',
                            ) as dbg:
                                dbg.write(redact_secrets(content_str) or "")
                            sys.stderr.write(
                                f"[!] LỖI PARSE SCHEMA: Model không trả về JSON hợp lệ: {jde}. "
                                f"Redacted dump saved to {dbg.name}\n",
                            )
                        else:
                            sys.stderr.write(
                                f"[!] LỖI PARSE SCHEMA: Model không trả về JSON hợp lệ: {jde}.\n",
                            )
                        sys.exit(EXIT_SYSTEM_STRICT)

                if not isinstance(parsed_verdict, dict):
                    sys.stderr.write(f"[!] LỖI SCHEMA AUDIT: Parsed verdict is not a JSON object (got {type(parsed_verdict).__name__})\n")
                    sys.exit(EXIT_SYSTEM_STRICT)

                is_valid, validation_msg = validate_audit_verdict(parsed_verdict)
                if not is_valid:
                    sys.stderr.write(f"[!] LỖI SCHEMA AUDIT: {validation_msg}\n")
                    sys.exit(EXIT_SYSTEM_STRICT)

                return parsed_verdict, current_model

        except urllib.error.HTTPError as http_err:
            err_code = http_err.code
            err_body = ""
            try:
                err_body = http_err.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            # HTTP 401 / 402: Authentication / Billing -> Fail Fast (Exit code 2)
            if err_code in (401, 402):
                if err_code == 401:
                    sys.stderr.write(
                        "[!] LỖI XÁC THỰC (HTTP 401): DEEPSEEK_API_KEY không hợp lệ hoặc bị thu hồi!\n"
                    )
                else:
                    sys.stderr.write(
                        "[!] LỖI TÀI KHOẢN (HTTP 402): Tài khoản DeepSeek hết số dư. Vui lòng nạp tiền tại https://platform.deepseek.com\n"
                    )
                sys.exit(EXIT_AUTH_QUOTA)

            # HTTP 400 / 404 / 422: Check if model error allows fallback
            if err_code in (400, 404, 422):
                is_model_error = "model" in err_body.lower() and any(
                    kw in err_body.lower() for kw in ("not exist", "not found", "invalid", "unsupported")
                )
                if is_model_error and not model_fallback_attempted and current_model != "deepseek-chat":
                    sys.stderr.write(
                        f"[*] CẢNH BÁO: Model '{current_model}' không tồn tại. Tự động fallback sang 'deepseek-chat'...\n"
                    )
                    current_model = "deepseek-chat"
                    model_fallback_attempted = True
                    continue

                sys.stderr.write(
                    f"[!] LỖI CẤU HÌNH (HTTP {err_code}): Yêu cầu không hợp lệ. Chi tiết: {err_body}\n"
                )
                sys.exit(EXIT_CONFIG_USAGE)

            # HTTP 429: Cloud rate limit
            if err_code == 429:
                if attempt >= 3:
                    sys.stderr.write(
                        "[!] QUÁ TẢI (HTTP 429): DeepSeek rate limit đã vượt quá 3 lần retry. Thử lại sau.\n"
                    )
                    sys.exit(EXIT_AUTH_QUOTA)

                retry_after_val: Optional[float] = None
                retry_header = http_err.headers.get("Retry-After")
                if retry_header:
                    try:
                        retry_after_val = float(retry_header)
                    except ValueError:
                        pass

                sleep_time = calculate_sleep_duration(attempt, retry_after=retry_after_val, deadline=deadline)

                # FLAW-004: Fail-fast if remaining monotonic time < 8.0s
                remaining_after_sleep = deadline - (time.monotonic() + sleep_time)
                if remaining_after_sleep < MIN_INFER_WINDOW:
                    sys.stderr.write(
                        f"[!] QUÁ TẢI (Fail-Fast): Thời gian còn lại ({remaining_after_sleep:.1f}s) < {MIN_INFER_WINDOW}s. "
                        "Hủy retry để tránh lãng phí token.\n"
                    )
                    sys.exit(EXIT_TIMEOUT_NETWORK)

                time.sleep(sleep_time)
                continue

            # HTTP 500 / 502 / 503 / 504: Cloud Outage
            if err_code in (500, 502, 503, 504):
                if attempt >= 3:
                    sys.stderr.write(
                        f"[!] LỖI MÁY CHỦ (HTTP {err_code}): Cloud DeepSeek không khả dụng sau 3 lần thử.\n"
                    )
                    sys.exit(EXIT_TIMEOUT_NETWORK)

                sleep_time = calculate_sleep_duration(attempt, deadline=deadline)
                remaining_after_sleep = deadline - (time.monotonic() + sleep_time)
                if remaining_after_sleep < MIN_INFER_WINDOW:
                    sys.stderr.write(
                        f"[!] LỖI MÁY CHỦ (Fail-Fast): Thời gian còn lại ({remaining_after_sleep:.1f}s) < {MIN_INFER_WINDOW}s. Hủy retry.\n"
                    )
                    sys.exit(EXIT_TIMEOUT_NETWORK)

                time.sleep(sleep_time)
                continue

            # Unhandled HTTP error
            sys.stderr.write(f"[!] LỖI HTTP {err_code}: {err_body}\n")
            sys.exit(EXIT_CONFIG_USAGE)

        except (urllib.error.URLError, TimeoutError) as url_err:
            # Network drop, socket timeout, connection refused
            err_msg = getattr(url_err, "reason", str(url_err))
            if attempt >= 3:
                sys.stderr.write(f"[!] LỖI KẾT NỐI: Mạng hoặc Timeout sau 3 lần thử: {err_msg}\n")
                sys.exit(EXIT_TIMEOUT_NETWORK)

            sleep_time = calculate_sleep_duration(attempt, deadline=deadline)
            remaining_after_sleep = deadline - (time.monotonic() + sleep_time)
            if remaining_after_sleep < MIN_INFER_WINDOW:
                sys.stderr.write(
                    f"[!] LỖI KẾT NỐI (Fail-Fast): Thời gian còn lại ({remaining_after_sleep:.1f}s) < {MIN_INFER_WINDOW}s. Hủy retry.\n"
                )
                sys.exit(EXIT_TIMEOUT_NETWORK)

            time.sleep(sleep_time)
            continue

    sys.stderr.write("[!] HẾT SỐ LẦN THỬ: Không nhận được phản hồi hợp lệ từ DeepSeek API!\n")
    sys.exit(EXIT_TIMEOUT_NETWORK)


def main() -> None:
    parser = StrictArgumentParser(
        description="Omni-Auditor Strict Architecture Gatekeeper (DeepSeek-V4.1-Flash)"
    )
    parser.add_argument("--file", "-f", type=str, help="Đường dẫn file RFC, SDD bundle, hoặc Git diff cần audit")
    parser.add_argument("--prompt", "-p", type=str, help="Nội dung kiến trúc hoặc câu hỏi trực tiếp")
    parser.add_argument("--out", "-o", type=str, help="Đường dẫn lưu artifact kết quả phản biện (.md hoặc .json)")
    parser.add_argument("--timeout", "-t", type=float, default=DEFAULT_TIMEOUT, help=f"Thời gian chờ tối đa (giây, mặc định: {DEFAULT_TIMEOUT}s)")
    parser.add_argument("--mode", "-m", choices=["rfc", "code"], default="rfc", help="Chế độ audit ('rfc' hoặc 'code', mặc định: 'rfc')")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Tên model DeepSeek (mặc định: '{DEFAULT_MODEL}')")
    parser.add_argument("--temperature", type=float, default=0.2, help="Nhiệt độ sinh text (0.0 đến 2.0, mặc định: 0.2)")
    parser.add_argument("--strict", action="store_true", default=False, help="Chế độ nghiêm ngặt: thoát mã 5 nếu verdict != APPROVED")
    parser.add_argument("--json", action="store_true", default=False, help="Xuất trực tiếp định dạng JSON thay vì Markdown")
    parser.add_argument("--api-base", type=str, default=None, help="DeepSeek API Base URL (mặc định: https://api.deepseek.com hoặc DEEPSEEK_API_BASE)")
    parser.add_argument("--allowed-root", type=str, default=None, help="Thư mục gốc cho phép (chống path traversal)")
    parser.add_argument("--workspace", "-w", type=str, default=None, help="Thư mục workspace cho ràng buộc cryptographic workspace_hash")

    args = parser.parse_args()

    # Validate that either --file or --prompt is specified
    if not args.file and not args.prompt:
        sys.stderr.write("[!] LỖI THAM SỐ: Bắt buộc phải cung cấp --file hoặc --prompt!\n")
        parser.print_usage(sys.stderr)
        sys.exit(EXIT_CONFIG_USAGE)

    # Clamp timeout between MIN_TIMEOUT and MAX_TIMEOUT
    effective_timeout = max(MIN_TIMEOUT, min(args.timeout, MAX_TIMEOUT))

    # Clamp temperature between 0.0 and 2.0
    effective_temperature = max(0.0, min(args.temperature, 2.0))

    # Resolve API Base URL
    api_base = args.api_base or os.environ.get("DEEPSEEK_API_BASE") or DEFAULT_API_BASE

    # Load API key (fails fast with code 2 if absent)
    api_key = load_api_key()

    target_file = "inline_prompt"
    raw_content = ""

    if args.file:
        validated_file = validate_path(args.file, allowed_root=args.allowed_root)
        target_file = os.path.basename(validated_file)
        try:
            with open(validated_file, "r", encoding="utf-8") as f:
                raw_content = f.read()
        except UnicodeDecodeError:
            sys.stderr.write(f"[!] LỖI FILE: File '{args.file}' không phải là text UTF-8 hợp lệ!\n")
            sys.exit(EXIT_CONFIG_USAGE)
        except Exception as e:
            sys.stderr.write(f"[!] LỖI FILE: Không thể đọc file '{args.file}': {e}\n")
            sys.exit(EXIT_CONFIG_USAGE)

    if args.prompt:
        if raw_content:
            raw_content = f"{raw_content}\n\n--- ADDITIONAL USER PROMPT ---\n{args.prompt}"
        else:
            raw_content = args.prompt

    # Zero-Trust Credential Redaction Pass (Principle II.2)
    sanitized_content = redact_credentials(raw_content)

    # Compute SHA-256 hash for cryptographic binding
    input_hash = f"sha256:{hashlib.sha256(sanitized_content.encode('utf-8')).hexdigest()}"

    # Build system prompt with conditional contract (FLAW-001)
    system_prompt = build_system_prompt(args.mode)

    # Execute request
    start_time = time.monotonic()
    verdict_data, final_model = execute_critic_request(
        api_key=api_key,
        api_base=api_base,
        model=args.model,
        system_prompt=system_prompt,
        user_content=sanitized_content,
        temperature=effective_temperature,
        timeout_budget=effective_timeout
    )
    elapsed = time.monotonic() - start_time

    verdict = verdict_data.get("verdict", "REJECTED")

    # Format output
    if args.json:
        output_text = json.dumps(verdict_data, indent=2, ensure_ascii=False)
    else:
        # Resolve explicit workspace directory for cryptographic binding (VULN-004, VULN-007)
        target_ws = args.workspace
        if not target_ws and args.file:
            target_ws = find_workspace_root(args.file)
        if not target_ws:
            target_ws = find_workspace_root(os.getcwd())

        output_text = format_markdown_report(
            data=verdict_data,
            target_file=target_file,
            input_hash=input_hash,
            model=final_model,
            workspace_dir=target_ws
        )

    # Write output artifact or print
    if args.out:
        out_path = os.path.realpath(os.path.normpath(args.out))
        try:
            out_dir = os.path.dirname(out_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            # Atomic file persistence: write to unique temp file then replace atomically
            temp_out = f"{out_path}.tmp.{os.getpid()}_{random.randint(1000, 9999)}"
            with open(temp_out, "w", encoding="utf-8") as f:
                f.write(output_text)
            os.replace(temp_out, out_path)
            print(f"[+] Đã lưu kết quả phản biện vào: {out_path} (hoàn thành trong {elapsed:.1f}s)")
        except Exception as e:
            sys.stderr.write(f"[!] LỖI GHI FILE: Không thể ghi artifact vào '{args.out}': {e}\n")
            sys.exit(EXIT_CONFIG_USAGE)
    else:
        print(f"\n[+] Phản biện hoàn tất từ {final_model} sau {elapsed:.1f}s (Verdict: {verdict}):\n")
        print("=" * 70)
        print(output_text)
        print("=" * 70)

    # Strict mode enforcement
    if args.strict and verdict != "APPROVED":
        sys.stderr.write(
            f"[!] STRICT MODE REJECTION: Kiến trúc không được duyệt (Verdict: {verdict}). Thoát mã {EXIT_SYSTEM_STRICT}.\n"
        )
        sys.exit(EXIT_SYSTEM_STRICT)

    # Standard exit code contract
    if verdict in ("APPROVED", "CONDITIONAL_PASS"):
        sys.exit(EXIT_APPROVED)
    else:
        sys.exit(EXIT_CRITIQUE_GENERATED)


if __name__ == "__main__":
    main()
