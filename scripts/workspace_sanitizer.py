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
import stat
import shutil
import tempfile
import unicodedata
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

DEFAULT_TRUST_DB = os.path.expanduser("~/.gemini/config/trusted_workspaces.json")

# Confusables mapping (TR39 Cyrillic, Greek, and Latin homoglyphs to ASCII equivalents - VULN-002)
CONFUSABLES_MAP = str.maketrans({
    # Latin lookalikes & dotless variants (VULN-002)
    '\u0131': 'i', '\u0130': 'I', '\u017f': 's', '\u0251': 'a',
    '\u0261': 'g', '\u026a': 'I', '\u028c': 'v', '\u028e': 'y',
    '\u212a': 'K', '\u212b': 'A',
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
    # Stroked consonants
    'đ': 'd', 'Đ': 'D',
})

# Precompiled regex for combining diacritical marks (Mn, Me) across Unicode blocks (VULN-002)
_RE_COMBINING_MARKS = re.compile(r"[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]")


# Exhaustive pre-compiled regex covering 100% of Unicode Cf (format), Cc (control), Zl/Zp (line/paragraph separators),
# and Tag characters (U+E0000..U+E007F) across all Unicode planes (VULN-101, VULN-004, SLO <5ms on 256 KiB).
_RE_UNICODE_FORMAT_AND_CONTROL = re.compile(
    r"[\U00000000-\U00000008\U0000000b-\U0000000c\U0000000e-\U0000001f\U0000007f-\U0000009f"
    r"\U000000ad\U00000600-\U00000605\U0000061c\U000006dd\U0000070f\U00000890-\U00000891\U000008e2"
    r"\U0000180e\U0000200b-\U0000200f\U00002028-\U0000202e\U00002060-\U00002064\U00002066-\U0000206f"
    r"\U0000feff\U0000fff9-\U0000fffb\U000110bd\U000110cd\U00013430-\U0001343f\U0001bca0-\U0001bca3"
    r"\U0001d173-\U0001d17a\U000e0000-\U000e007f]"
)


def sanitize_unicode_skeleton(text: str) -> str:
    """
    Applies full Unicode format/control filtering and confusable skeleton mapping (VULN-101, VULN-004, VULN-002).
    Decomposes NFD to strip combining diacritical marks via vectorized PCRE, neutralizing accented homoglyphs (í -> i).
    Exhaustively strips ALL Cf (format, zero-width, soft-hyphens, bidi controls, interlinear annotations U+FFF9..U+FFFB),
    Cc (control codes), Zl/Zp (line/paragraph separators U+2028/U+2029), and tag characters (U+E0000..U+E007F).
    Preserves standard whitespace (\\n, \\r, \\t). Completes in <5ms on 256 KiB upper bound.
    """
    if not text:
        return ""
    # 1. NFD decomposition to separate base letters from combining marks (VULN-002)
    decomposed = unicodedata.normalize("NFD", text)
    stripped_marks = _RE_COMBINING_MARKS.sub("", decomposed)
    norm = unicodedata.normalize("NFKC", stripped_marks)
    # 2. Translate Cyrillic, Greek homoglyphs & stroked consonants
    trans = norm.translate(CONFUSABLES_MAP)
    # 3. Vectorized stripping of format, control, separator, and tag characters (VULN-004)
    stripped = _RE_UNICODE_FORMAT_AND_CONTROL.sub("", trans)
    # 4. Final NFKC stabilization
    return unicodedata.normalize("NFKC", stripped)


# --------------------------------------------------------------------------- #
# Cross-Process File Lock (Companion .lock file to prevent os.replace conflict)
# --------------------------------------------------------------------------- #
class TrustFileLock:
    """Context manager for cross-process advisory lock on companion .lock file (canonical realpath - VULN-012)."""
    def __init__(self, target_path: str, timeout: float = 5.0):
        clean_target = os.path.normcase(os.path.realpath(os.path.abspath(target_path)))
        if clean_target.endswith(".lock"):
            self.lock_path = clean_target
        else:
            self.lock_path = f"{clean_target}.lock"
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.lock_path)), exist_ok=True)
        if os.path.islink(self.lock_path) or (hasattr(os.path, "isreparsepoint") and os.path.isreparsepoint(self.lock_path)):
            raise PermissionError(f"Security violation: lock file cannot be a symbolic link or reparse point: {self.lock_path}")
        start = time.time()
        self._fh = open(self.lock_path, "a+b")
        try:
            st = os.fstat(self._fh.fileno())
            if not stat.S_ISREG(st.st_mode):
                raise PermissionError(f"Security violation: lock file is not a regular file: {self.lock_path}")
            if sys.platform.startswith("win"):
                reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                if getattr(st, "st_file_attributes", 0) & reparse:
                    raise PermissionError(f"Security violation: lock file is a reparse point or symlink: {self.lock_path}")
            if getattr(st, "st_nlink", 1) > 1:
                raise PermissionError(f"Security violation: lock file has hard links: {self.lock_path}")
        except Exception:
            self._fh.close()
            self._fh = None
            raise

        if os.name == "nt":
            self._fh.seek(0, os.SEEK_END)
            if self._fh.tell() == 0:
                self._fh.write(b"\x00")
                self._fh.flush()
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
                if ((os.name == "nt" and getattr(exc, "winerror", None) in (32, 33, 36)) or
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
class TrustStoreUnreadableError(Exception):
    """Raised when the trust store cannot be reliably loaded due to I/O or schema failure (VULN-002)."""
    pass


def normalize_path(path: Any) -> str:
    """
    Normalizes path casing, directory separators, and resolves physical symlinks (VULN-WS-001).
    Ensures that symlinked directories are evaluated against their true physical target.
    Type-guarded: Rejects non-string inputs with empty string to prevent TypeError crashes (Defensive #2).
    """
    if not isinstance(path, (str, bytes, os.PathLike)) or not path:
        return ""
    try:
        path_str = os.fspath(path)
        if isinstance(path_str, bytes):
            path_str = path_str.decode("utf-8", errors="replace")
        expanded = os.path.expanduser(path_str)
        return os.path.normcase(os.path.realpath(os.path.abspath(expanded)))
    except Exception:
        return ""


def _load_trust_db_locked(db_path: str) -> Dict[str, List[str]]:
    """Loads and validates trust DB schema under lock with bounded retry before quarantine (VULN-106, VULN-002)."""
    if not os.path.exists(db_path):
        return {"trusted": []}

    last_exc = None
    for attempt in range(3):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("trusted"), list):
                # Defensive #2: Validate each item is a string
                cleaned_trusted = [p for p in data["trusted"] if isinstance(p, str)]
                data["trusted"] = cleaned_trusted
                return data
            raise ValueError("Schema mismatch: 'trusted' key must be a list of strings")
        except Exception as exc:
            last_exc = exc
            time.sleep(0.05 * (attempt + 1))

    # Only quarantine on provable syntax corruption (JSONDecodeError), never on transient errors or schema evolution (VULN-002)
    if isinstance(last_exc, json.JSONDecodeError):
        ts = int(time.time())
        bak = f"{db_path}.corrupt.{ts}.bak"
        try:
            if os.path.exists(db_path):
                shutil.copy2(db_path, bak)
                os.replace(db_path, bak)
                sys.stderr.write(f"[!] Warning: Repeatable corrupt trust DB quarantined to {bak} after 3 attempts: {last_exc}\n")
        except OSError:
            pass
        return {"trusted": []}

    # On transient I/O or schema failure, abort mutation path! (VULN-002)
    sys.stderr.write(f"[!] Warning: Trust DB read error ({type(last_exc).__name__}: {last_exc}); preserving file.\n")
    raise TrustStoreUnreadableError(f"Trust DB could not be loaded cleanly: {last_exc}")


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
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        return False
    norm_target = normalize_path(workspace_path)
    if not norm_target:
        return False
    db_path = os.path.expanduser(trust_db_path)
    if not os.path.exists(db_path):
        return False

    # Lock-free fast read path with retries
    for _ in range(3):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("trusted"), list):
                trusted_dirs = [normalize_path(p) for p in data["trusted"] if isinstance(p, str)]
                return norm_target in trusted_dirs
        except (OSError, json.JSONDecodeError):
            time.sleep(0.01)

    # Fallback to locked read if contention occurred
    try:
        with TrustFileLock(db_path, timeout=1.0):
            data = _load_trust_db_locked(db_path)
            trusted_dirs = [normalize_path(p) for p in data.get("trusted", []) if isinstance(p, str)]
            return norm_target in trusted_dirs
    except Exception:
        return False


def add_trusted_workspace(workspace_path: str, trust_db_path: str = DEFAULT_TRUST_DB) -> bool:
    """Adds a workspace directory to the trusted whitelist with atomic write and locking (VULN-002)."""
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        return False
    norm_target = normalize_path(workspace_path)
    if not norm_target:
        return False
    db_path = os.path.expanduser(trust_db_path)
    with TrustFileLock(db_path, timeout=5.0):
        try:
            data = _load_trust_db_locked(db_path)
        except TrustStoreUnreadableError as err:
            sys.stderr.write(f"[!] Refusing to mutate trust DB due to load failure: {err}\n")
            return False
        trusted = data.get("trusted", [])
        normalized_list = [normalize_path(p) for p in trusted if isinstance(p, str)]
        if norm_target not in normalized_list:
            # VULN-003: Persist canonical physical realpath to prevent symlink retargeting attacks
            trusted.append(norm_target)
            data["trusted"] = trusted
            _atomic_save_trust_db(db_path, data)
            return True
        return False


def remove_trusted_workspace(workspace_path: str, trust_db_path: str = DEFAULT_TRUST_DB) -> bool:
    """Removes a workspace directory from the trusted whitelist with atomic write and locking (VULN-002)."""
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        return False
    norm_target = normalize_path(workspace_path)
    if not norm_target:
        return False
    db_path = os.path.expanduser(trust_db_path)
    if not os.path.exists(db_path):
        return False
    with TrustFileLock(db_path, timeout=5.0):
        try:
            data = _load_trust_db_locked(db_path)
        except TrustStoreUnreadableError as err:
            sys.stderr.write(f"[!] Refusing to mutate trust DB due to load failure: {err}\n")
            return False
        trusted = data.get("trusted", [])
        new_trusted = [p for p in trusted if isinstance(p, str) and normalize_path(p) != norm_target]
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
        r"\b(ignore|disregard|forget)\s+(?:all\s+)?(?:of\s+the\s+)?(?:the\s+)?(?:all\s+)?(?:previous|prior|above)\s+(instructions|prompts|rules|commands|context)|"
        r"\bforget\s+(all\s+)?(everything|all)\b|"
        r"\b(print|reveal|show|dump)\s+(?:all\s+)?(?:of\s+the\s+)?(?:the\s+)?(?:all\s+)?(?:previous|prior|system|initial)\s+(instructions|prompts|rules|context)|"
        r"\bact\s+as\s+(?:an?\s+)?(?:the\s+)?(system\s+administrator|administrator|root|admin|superuser)\b|"
        r"\brepeat\s+(all\s+)?(the\s+)?(text|words|instructions)\s+above\b|"
        r"system\s+override|\byou\s+are\s+now\b|developer\s+mode\s*:\s*on|\bdan\s+mode\b|\bjailbreak\b|"
        r"(?:bỏ|bo)\s+qua\s+(?:tất\s+cả|tat\s+ca\s+)?(?:toàn\s+bộ|toan\s+bo|tất\s+cả|tat\s+ca|các|cac|những|nhung)?\s*(?:chỉ\s+dẫn|chi\s+dan|hướng\s+dẫn|huong\s+dan|quy\s+tắc|quy\s+tac)|"
        r"(?:quên|quen)\s+(?:hết|het|toàn\s+bộ|toan\s+bo|tất\s+cả|tat\s+ca)?\s*(?:hướng\s+dẫn|huong\s+dan|chỉ\s+dẫn|chi\s+dan)|"
        r"in\s+ra\s+(?:các|cac)?\s*(?:chỉ\s+dẫn|chi\s+dan|hướng\s+dẫn|huong\s+dan|system\s+prompt)|"
        r"(?:lặp|lap)\s+(?:lại|lai)\s+(?:toàn\s+bộ|toan\s+bo\s+)?(?:văn\s+bản|van\s+ban|nội\s+dung|noi\s+dung)\s+(?:phía\s+trên|phia\s+tren)|"
        r"(?:đóng|dong)\s+vai\s+(?:quản\s+trị\s+viên|quan\s+tri\s+vien|admin)|"
        r"(?:từ|tu)\s+(?:bây|bay)\s+(?:giờ|gio)\s+(?:bạn|ban)\s+(?:là|la)|(?:bật|bat)\s+(?:chế\s+độ|che\s+do)\s+(?:nhà|nha)\s+(?:phát\s+triển|phat\s+trien)",
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

        # 1. Payload size guard (Anti-DOS, VULN-009: pre-check string length before encoding)
        if len(content) > cls.MAX_PAYLOAD_BYTES:
            return False, [f"[Size] Kích thước nội dung vượt trần bảo vệ 256 KiB trong {filepath}"]
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

    @classmethod
    def scan_injection_only(cls, content: str, filepath: str = "") -> Tuple[bool, List[str]]:
        """
        Fast check specifically for cognitive manipulation / prompt injection (VULN-001).
        Does not falsely trigger on benign network/shell words (e.g., 'curl', 'wget') in rule titles or descriptions.
        """
        if not content:
            return True, []
        cleaned = sanitize_unicode_skeleton(content)
        if cls._PAT_INJECTION.search(cleaned):
            return False, [f"[Injection] System Prompt override detected in {filepath}"]
        return True, []


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
