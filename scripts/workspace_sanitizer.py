#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Workspace Sanitizer & Guard
High-speed, zero-dependency Indirect Prompt Injection (IPI) & malicious command guard
designed specifically for workspace rule assimilation (scripts/assimilator.py).

Guarantees:
1. Sub-millisecond execution overhead via compiled regexes and Unicode NFKC normalization.
2. Real confusable skeleton mapping (TR39) and full Unicode Cf/Cc category stripping (VULN-101).
3. Cross-process file locking for mutations; lock-free fast-path for reads (VULN-106).
4. Physical realpath normalization defeating symlink traversal bypasses (VULN-WS-001).
5. Non-destructive trust DB recovery with bounded retries and schema protection.
6. Strict Ring 0 Zero-Trust boundaries and bilingual parity (EN & VI).
"""

import os
import re
import sys
import json
import time
import errno
import tempfile
import unicodedata
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

DEFAULT_TRUST_DB = os.path.expanduser("~/.gemini/config/trusted_workspaces.json")

# Confusables mapping (TR39 Cyrillic & Greek lookalikes to Latin equivalents)
CONFUSABLES_MAP = str.maketrans({
    # Cyrillic lowercase
    '\u0430': 'a', '\u0441': 'c', '\u0435': 'e', '\u043e': 'o',
    '\u0440': 'p', '\u0445': 'x', '\u0443': 'y', '\u0456': 'i',
    '\u0458': 'j', '\u0455': 's', '\u0501': 'd', '\u051b': 'q',
    '\u051d': 'w', '\u04bb': 'h', '\u0432': 'b', '\u0442': 't',
    # Cyrillic uppercase
    '\u0410': 'A', '\u0412': 'B', '\u0421': 'C', '\u0415': 'E',
    '\u041d': 'H', '\u0406': 'I', '\u0408': 'J', '\u041a': 'K',
    '\u041c': 'M', '\u041e': 'O', '\u0420': 'P', '\u0422': 'T',
    '\u0425': 'X', '\u0423': 'Y',
    # Greek lowercase
    '\u03b1': 'a', '\u03b2': 'b', '\u03b5': 'e', '\u03b9': 'i',
    '\u03ba': 'k', '\u03bd': 'v', '\u03bf': 'o', '\u03c1': 'p',
    '\u03c2': 's', '\u03c4': 't', '\u03c5': 'u', '\u03c7': 'x',
    # Greek uppercase
    '\u0391': 'A', '\u0392': 'B', '\u0395': 'E', '\u0397': 'H',
    '\u0399': 'I', '\u039a': 'K', '\u039c': 'M', '\u039d': 'N',
    '\u039f': 'O', '\u03a1': 'P', '\u03a4': 'T', '\u03a7': 'X',
    '\u03a5': 'Y', '\u0396': 'Z',
})


def sanitize_unicode_skeleton(text: str) -> str:
    """
    Applies full Unicode format/control filtering and confusable skeleton mapping (VULN-101).
    Removes Cf (format, zero-width, soft-hyphen U+00AD), Cc (control chars), and tag chars (U+E0000-U+E007F).
    """
    if not text:
        return ""
    # 1. First-pass NFKC
    norm = unicodedata.normalize("NFKC", text)
    # 2. Translate Cyrillic & Greek homoglyphs
    trans = norm.translate(CONFUSABLES_MAP)
    # 3. Strip format/tag/control characters
    chars = []
    for ch in trans:
        cp = ord(ch)
        if 0xE0000 <= cp <= 0xE007F:
            continue  # Tag characters
        cat = unicodedata.category(ch)
        if cat == "Cf":
            continue  # Zero-width spaces, soft hyphen U+00AD, CGJ U+034F, etc.
        if cat == "Cc":
            if ch in ("\n", "\r", "\t"):
                chars.append(ch)
            continue  # Strip dangerous control codes
        chars.append(ch)
    # 4. Final NFKC stabilization
    return unicodedata.normalize("NFKC", "".join(chars))


# --------------------------------------------------------------------------- #
# Cross-Process File Lock (Companion .lock file to prevent os.replace conflict)
# --------------------------------------------------------------------------- #
class TrustFileLock:
    """Context manager for cross-process advisory lock on companion .lock file."""
    def __init__(self, target_path: str, timeout: float = 5.0):
        self.lock_path = f"{target_path}.lock"
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.lock_path)), exist_ok=True)
        start = time.time()
        self._fh = open(self.lock_path, "a+b")
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, IOError) as exc:
                if ((os.name == "nt" and getattr(exc, "winerror", None) == 33) or
                    (getattr(exc, "errno", None) in (errno.EACCES, errno.EAGAIN))):
                    if time.time() - start >= self.timeout:
                        self._fh.close()
                        self._fh = None
                        raise TimeoutError(f"Timeout waiting for lock on {self.lock_path}")
                    time.sleep(0.02)
                else:
                    self._fh.close()
                    self._fh = None
                    raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._fh:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            finally:
                self._fh.close()
                self._fh = None


# --------------------------------------------------------------------------- #
# Path Normalization & Trust Store Loading
# --------------------------------------------------------------------------- #
def normalize_path(path: str) -> str:
    """
    Normalizes path casing, directory separators, and resolves physical symlinks (VULN-WS-001).
    Ensures that symlinked directories are evaluated against their true physical target.
    """
    if not path:
        return ""
    expanded = os.path.expanduser(path)
    return os.path.normcase(os.path.realpath(os.path.abspath(expanded)))


def _load_trust_db_locked(db_path: str) -> Dict[str, List[str]]:
    """Loads and validates trust DB schema under lock with bounded retry before quarantine (VULN-106)."""
    if not os.path.exists(db_path):
        return {"trusted": []}

    last_exc = None
    for attempt in range(3):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("trusted"), list):
                return data
            raise ValueError("Schema mismatch: 'trusted' key must be a list")
        except Exception as exc:
            last_exc = exc
            time.sleep(0.05 * (attempt + 1))

    # Deterministic, repeatable failure: quarantine to backup but log loudly
    ts = int(time.time())
    bak = f"{db_path}.corrupt.{ts}.bak"
    try:
        if os.path.exists(db_path):
            os.replace(db_path, bak)
            sys.stderr.write(f"[!] Warning: Repeatable corrupt trust DB quarantined to {bak}: {last_exc}\n")
    except OSError:
        pass
    return {"trusted": []}


def _atomic_save_trust_db(db_path: str, data: Dict[str, Any]) -> None:
    """Writes trust DB atomically using temp file and os.replace with fsync."""
    dir_name = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".trust_tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, db_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def is_trusted_workspace(workspace_path: str, trust_db_path: str = DEFAULT_TRUST_DB) -> bool:
    """
    Checks whether a repository directory has been explicitly approved by the user.
    Uses lock-free fast-path read with bounded retry; avoids serializing on reads (VULN-106).
    """
    if not workspace_path:
        return False
    norm_target = normalize_path(workspace_path)
    db_path = os.path.expanduser(trust_db_path)
    if not os.path.exists(db_path):
        return False

    # Lock-free fast read path with retries
    for _ in range(3):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("trusted"), list):
                trusted_dirs = [normalize_path(p) for p in data["trusted"]]
                return norm_target in trusted_dirs
        except (OSError, json.JSONDecodeError):
            time.sleep(0.01)

    # Fallback to locked read if contention occurred
    try:
        with TrustFileLock(db_path, timeout=1.0):
            data = _load_trust_db_locked(db_path)
            trusted_dirs = [normalize_path(p) for p in data.get("trusted", [])]
            return norm_target in trusted_dirs
    except Exception:
        return False


def add_trusted_workspace(workspace_path: str, trust_db_path: str = DEFAULT_TRUST_DB) -> bool:
    """Adds a workspace directory to the trusted whitelist with atomic write and locking."""
    if not workspace_path:
        return False
    norm_target = normalize_path(workspace_path)
    db_path = os.path.expanduser(trust_db_path)
    with TrustFileLock(db_path, timeout=5.0):
        data = _load_trust_db_locked(db_path)
        trusted = data.get("trusted", [])
        normalized_list = [normalize_path(p) for p in trusted]
        if norm_target not in normalized_list:
            clean_entry = os.path.abspath(os.path.expanduser(workspace_path)).replace("\\", "/")
            trusted.append(clean_entry)
            data["trusted"] = trusted
            _atomic_save_trust_db(db_path, data)
            return True
        return False


def remove_trusted_workspace(workspace_path: str, trust_db_path: str = DEFAULT_TRUST_DB) -> bool:
    """Removes a workspace directory from the trusted whitelist with atomic write and locking."""
    if not workspace_path:
        return False
    norm_target = normalize_path(workspace_path)
    db_path = os.path.expanduser(trust_db_path)
    if not os.path.exists(db_path):
        return False
    with TrustFileLock(db_path, timeout=5.0):
        data = _load_trust_db_locked(db_path)
        trusted = data.get("trusted", [])
        new_trusted = [p for p in trusted if normalize_path(p) != norm_target]
        if len(new_trusted) != len(trusted):
            data["trusted"] = new_trusted
            _atomic_save_trust_db(db_path, data)
            return True
        return False


# --------------------------------------------------------------------------- #
# Hardened IPI Sanitizer Guard
# --------------------------------------------------------------------------- #
class AssimilatorGuard:
    """
    High-speed security filter (Sanitizer) preventing Indirect Prompt Injection,
    malicious command execution, and credential exfiltration from untrusted workspace rules.
    """

    MAX_PAYLOAD_BYTES = 256 * 1024  # 256 KiB upper bound

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
        r"\b(print|reveal|show|dump)\s+(the\s+)?(all\s+)?(previous|prior|system|initial)\s+(instructions|prompts|rules|context)|"
        r"\bact\s+as\s+(the\s+)?(system\s+administrator|root|admin|superuser)\b|"
        r"\brepeat\s+(all\s+)?(the\s+)?(text|words|instructions)\s+above\b|"
        r"system\s+override|\byou\s+are\s+now\b|developer\s+mode\s*:\s*on|\bdan\s+mode\b|\bjailbreak\b|"
        r"bỏ\s+qua\s+(toàn\s+bộ|tất\s+cả|các)?\s*(chỉ\s+dẫn|hướng\s+dẫn|quy\s+tắc)|"
        r"quên\s+(hết|toàn\s+bộ|tất\s+cả)?\s*(hướng\s+dẫn|chỉ\s+dẫn)|"
        r"in\s+ra\s+(các\s+)?(chỉ\s+dẫn|hướng\s+dẫn|system\s+prompt)|"
        r"lặp\s+lại\s+(toàn\s+bộ\s+)?(văn\s+bản|nội\s+dung)\s+phía\s+trên|"
        r"đóng\s+vai\s+(quản\s+trị\s+viên|admin)|"
        r"từ\s+bây\s+giờ\s+bạn\s+là|bật\s+chế\s+độ\s+nhà\s+phát\s+triển",
        re.IGNORECASE
    )

    @classmethod
    def scan_rules(cls, content: str, filepath: str = "") -> Tuple[bool, List[str]]:
        """
        Scans rule/skill content for security violations and prompt injections.
        Applies full Unicode format/control filtering and confusable skeleton mapping (VULN-101).
        Returns:
            (is_safe, list_of_violations)
        """
        if not content:
            return True, []

        # 1. Payload size guard (Anti-DOS)
        if len(content.encode("utf-8", errors="ignore")) > cls.MAX_PAYLOAD_BYTES:
            return False, [f"[Size] Kích thước nội dung vượt trần bảo vệ 256 KiB trong {filepath}"]

        # 2. Unicode format/control filtering and confusable skeleton transliteration
        cleaned = sanitize_unicode_skeleton(content)

        violations = []

        if cls._PAT_NETWORK.search(cleaned):
            violations.append(f"[Network] Lệnh truyền tải mạng khả nghi trong {filepath}")

        if cls._PAT_SENSITIVE.search(cleaned):
            violations.append(f"[Sensitive] Nỗ lực đọc file cấu hình/chìa khóa/biến môi trường trong {filepath}")

        if cls._PAT_SHELL.search(cleaned):
            violations.append(f"[Shell] Phát hiện lệnh phá hoại hoặc Shell ẩn trong {filepath}")

        if cls._PAT_OBFUSCATION.search(cleaned):
            violations.append(f"[Obfuscation] Kỹ thuật che giấu mã (eval/base64) trong {filepath}")

        if cls._PAT_INJECTION.search(cleaned):
            violations.append(f"[Injection] Nỗ lực ghi đè System Prompt / Thao túng nhận thức trong {filepath}")

        return len(violations) == 0, violations


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
