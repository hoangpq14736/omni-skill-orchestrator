#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Workspace Sanitizer & Guard
High-speed, zero-dependency Indirect Prompt Injection (IPI) & malicious command guard
designed specifically for workspace rule assimilation (scripts/assimilator.py).

Guarantees sub-millisecond execution overhead via module-level compiled regexes,
strict Ring 0 Zero-Trust boundaries, and bilingual parity (EN & VI).
"""

import os
import re
import sys
import json
from typing import Tuple, List, Optional

DEFAULT_TRUST_DB = os.path.expanduser("~/.gemini/config/trusted_workspaces.json")


class AssimilatorGuard:
    """
    High-speed security filter (Sanitizer) preventing Indirect Prompt Injection,
    malicious command execution, and credential exfiltration from untrusted workspace rules.
    """

    # 1. Network & Exfiltration: Prevents outbound data leak and reverse shells
    _PAT_NETWORK = re.compile(
        r"\b(curl|wget|Invoke-WebRequest|iwr|irm|Invoke-RestMethod|Start-BitsTransfer|netcat|telnet|ftp|ping)\b|"
        r"nc\s+-e|>\s*/dev/(tcp|udp)/|urllib\.request|requests\.(post|get|put)|http\.client|socket\.socket",
        re.IGNORECASE
    )

    # 2. Sensitive Files, Credentials & Environment Dump
    _PAT_SENSITIVE = re.compile(
        r"\.env\b|id_rsa|id_ed25519|\.aws[/\\]credentials|\.kube[/\\]config|"
        r"/etc/passwd|/etc/shadow|[~%][^/\n\\]*ssh[/\\]|os\.environ|process\.env|"
        r"\$env:[a-zA-Z0-9_]+|\bprintenv\b",
        re.IGNORECASE
    )

    # 3. Malicious System Execution & Obfuscated Shell Commands
    _PAT_SHELL = re.compile(
        r"rm\s+-rf|chmod\s+777|\bchown\b|\bmkfifo\b|"
        r"(powershell|pwsh)[^\n]*?(-e|-encodedcommand)\b|"
        r"\biex\s*\(|\bInvoke-Expression\b|cmd\.exe\s+/c|/bin/(ba)?sh\s+-c|"
        r"del\s+/[fsq]|rmdir\s+/[sq]",
        re.IGNORECASE
    )

    # 4. Obfuscation Techniques
    _PAT_OBFUSCATION = re.compile(
        r"base64\s+-d|eval\s*\(|exec\s*\(|__import__\s*\(|"
        r"\[System\.Convert\]::FromBase64String|certutil\s+-decode",
        re.IGNORECASE
    )

    # 5. Cognitive Manipulation (Jailbreak, System Override, IPI in EN & VI)
    _PAT_INJECTION = re.compile(
        r"\b(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|commands|context)|"
        r"\bforget\s+(all\s+)?(everything|all)\b|"
        r"system\s+override|\byou\s+are\s+now\b|developer\s+mode\s*:\s*on|\bdan\s+mode\b|"
        r"bỏ\s+qua\s+(toàn\s+bộ|tất\s+cả|các)?\s*(chỉ\s+dẫn|hướng\s+dẫn|quy\s+tắc)|"
        r"quên\s+(hết|toàn\s+bộ|tất\s+cả)?\s*(hướng\s+dẫn|chỉ\s+dẫn)|"
        r"từ\s+bây\s+giờ\s+bạn\s+là|bật\s+chế\s+độ\s+nhà\s+phát\s+triển",
        re.IGNORECASE
    )

    @classmethod
    def scan_rules(cls, content: str, filepath: str = "") -> Tuple[bool, List[str]]:
        """
        Scans rule/skill content for security violations and prompt injections.
        Returns:
            (is_safe, list_of_violations)
        """
        if not content:
            return True, []

        violations = []

        if cls._PAT_NETWORK.search(content):
            violations.append(f"[Network] Lệnh truyền tải mạng khả nghi trong {filepath}")

        if cls._PAT_SENSITIVE.search(content):
            violations.append(f"[Sensitive] Nỗ lực đọc file cấu hình/chìa khóa/biến môi trường trong {filepath}")

        if cls._PAT_SHELL.search(content):
            violations.append(f"[Shell] Phát hiện lệnh phá hoại hoặc Shell ẩn trong {filepath}")

        if cls._PAT_OBFUSCATION.search(content):
            violations.append(f"[Obfuscation] Kỹ thuật che giấu mã (eval/base64) trong {filepath}")

        if cls._PAT_INJECTION.search(content):
            violations.append(f"[Injection] Nỗ lực ghi đè System Prompt / Thao túng nhận thức trong {filepath}")

        return len(violations) == 0, violations


def normalize_path(path: str) -> str:
    """Normalizes path casing and directory separators across Windows and POSIX."""
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(path))))


def is_trusted_workspace(workspace_path: str, trust_db_path: str = DEFAULT_TRUST_DB) -> bool:
    """
    Checks whether a repository directory has been explicitly approved by the user.
    Uses case-normalized matching for Windows compatibility.
    """
    if not workspace_path:
        return False
    norm_target = normalize_path(workspace_path)
    db_path = os.path.expanduser(trust_db_path)
    if not os.path.exists(db_path):
        return False
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            trusted_dirs = [normalize_path(p) for p in data.get("trusted", [])]
            return norm_target in trusted_dirs
    except Exception:
        return False


def add_trusted_workspace(workspace_path: str, trust_db_path: str = DEFAULT_TRUST_DB) -> bool:
    """Adds a workspace directory to the trusted whitelist."""
    norm_target = normalize_path(workspace_path)
    db_path = os.path.expanduser(trust_db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    trusted = []
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                trusted = json.load(f).get("trusted", [])
        except Exception:
            trusted = []
    normalized_list = [normalize_path(p) for p in trusted]
    if norm_target not in normalized_list:
        trusted.append(os.path.abspath(workspace_path).replace("\\", "/"))
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump({"trusted": trusted}, f, indent=2, ensure_ascii=False)
        return True
    return False


def remove_trusted_workspace(workspace_path: str, trust_db_path: str = DEFAULT_TRUST_DB) -> bool:
    """Removes a workspace directory from the trusted whitelist."""
    norm_target = normalize_path(workspace_path)
    db_path = os.path.expanduser(trust_db_path)
    if not os.path.exists(db_path):
        return False
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            trusted = json.load(f).get("trusted", [])
        new_trusted = [p for p in trusted if normalize_path(p) != norm_target]
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump({"trusted": new_trusted}, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Omni-Kernel Workspace Trust & Sanitizer Utility")
    parser.add_argument("--check", help="Check if workspace path is trusted")
    parser.add_argument("--trust", help="Add workspace path to trusted list")
    parser.add_argument("--untrust", help="Remove workspace path from trusted list")
    parser.add_argument("--scan-file", help="Scan a specific file for IPI / security violations")
    args = parser.parse_args()

    if args.check:
        trusted = is_trusted_workspace(args.check)
        status = "TRUSTED (Bypass Sanitizer)" if trusted else "UNTRUSTED (Sanitizer Guard Active)"
        print(f"[{status}] {os.path.abspath(args.check)}")
    elif args.trust:
        ok = add_trusted_workspace(args.trust)
        print(f"✔ Workspace whitelisted: {os.path.abspath(args.trust)}" if ok else "Already in trusted store.")
    elif args.untrust:
        ok = remove_trusted_workspace(args.untrust)
        print(f"✔ Workspace removed from whitelist: {os.path.abspath(args.untrust)}" if ok else "Not found in trusted store.")
    elif args.scan_file:
        if os.path.isfile(args.scan_file):
            with open(args.scan_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            safe, violations = AssimilatorGuard.scan_rules(content, args.scan_file)
            if safe:
                print(f"✔ [SAFE] {args.scan_file} passed all security checks.")
            else:
                print(f"❌ [UNSAFE] Violations detected in {args.scan_file}:")
                for v in violations:
                    print(f"   - {v}")
        else:
            print(f"[!] File not found: {args.scan_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
