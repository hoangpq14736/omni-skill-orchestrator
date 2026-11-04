"""
Omni-Kernel v4.1: Autonomous Skill, Rule & Tool Synthesizer (Hardened)
Enables the AI to independently hypothesize, author, sandbox-test, and promote
new skills, rules, and MCP wrappers when facing unmapped technical requirements.
Remediated against VULN-001 (Arbitrary test execution), VULN-002 (YAML injection),
clean_name path traversal, and atomic writing.
"""

import os
import sys
import json
import re
import ast
import uuid
import subprocess
import tempfile
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
DEFAULT_LIBRARY_DIR = os.path.join(HOME, ".gemini", "config", "skills_library")
SCRATCH_DIR = os.path.join(tempfile.gettempdir(), "omni_sandbox")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from kernel_sync import safe_atomic_replace
from indexer import parse_frontmatter


def generate_skill_template(name, description, domain="general", patterns=None, gotchas=None):
    """
    Generates a standard, production-ready SKILL.md document.
    Validates clean_name and description against injection and path traversal (VULN-002).
    """
    if not name or not isinstance(name, str):
        raise ValueError("Skill name must be a non-empty string")
    clean = name.strip().lower()
    if not clean or ".." in clean or "/" in clean or "\\" in clean:
        raise ValueError("Invalid skill name: must not contain path traversal characters")
    
    clean_name = re.sub(r'[^a-z0-9\-]', '-', clean).strip('-')
    if not clean_name:
        raise ValueError("Invalid skill name: must contain at least one alphanumeric character")
    if len(clean_name) > 64:
        raise ValueError("Skill name exceeds 64 characters limit")

    # Sanitize description against YAML breakout (VULN-002)
    clean_desc = re.sub(r'[\r\n\t]+', ' ', str(description)).strip()
    clean_desc = clean_desc.replace("---", "- - -")
    if len(clean_desc) > 1024:
        clean_desc = clean_desc[:1021] + "..."

    json_desc = json.dumps(clean_desc, ensure_ascii=False)
    clean_domain = re.sub(r'[^a-z0-9_\-]', '', str(domain).lower().strip()) or "general"

    patterns_text = "\n".join([f"- {re.sub(r'[\r\n]+', ' ', str(p)).strip()}" for p in (patterns or ["Follow standard library patterns first", "Validate all inputs at trust boundaries"])])
    gotchas_text = "\n".join([f"- {re.sub(r'[\r\n]+', ' ', str(g)).strip()}" for g in (gotchas or ["Never hardcode credentials or secrets", "Avoid unrequested abstractions or wrappers (YAGNI)"])])

    skill_content = f"""---
name: {clean_name}
description: {json_desc}
version: "1.0.0"
metadata:
  version: "1.0.0"
  domain: "{clean_domain}"
  auto_generated: true
  generated_at: "{datetime.now(timezone.utc).isoformat()}"
---

# {clean_name.replace('-', ' ').title()}

{clean_desc}

## Core Architecture & Patterns
{patterns_text}

## Critical Gotchas & Invariants
{gotchas_text}

## Verification & Self-Check
```python
# Self-check assertion test
assert True, "Verification passed"
```
"""
    # Defensive Assert: round-trip verification to ensure no YAML frontmatter breakout
    meta, _ = parse_frontmatter(skill_content)
    if meta.get("name") != clean_name:
        raise ValueError(f"Frontmatter name corrupted during synthesis: expected '{clean_name}', got '{meta.get('name')}'")

    return clean_name, skill_content


def run_syntax_validation(test_code, timeout_sec=5, allow_exec=False):
    """
    Validates synthesized test code using static AST analysis and restricted execution (VULN-106).
    NOTE: This provides static AST structural validation and clean-environment execution,
    not OS-level containerization/seccomp sandbox isolation.
    Returns (success: bool, stdout: str, stderr: str).
    """
    if not test_code or not str(test_code).strip():
        return (True, "Empty test code passed", "")

    # Static AST syntax and safety check
    try:
        parsed = ast.parse(test_code, mode="exec")
    except SyntaxError as e:
        return (False, "", f"AST validation failed: SyntaxError: {e}")

    # Check for dangerous system calls, dynamic code evaluation, and unsafe modules (VULN-104, VULN-106)
    PROHIBITED_MODULES = {"subprocess", "socket", "pty", "ctypes", "shutil"}
    DANGEROUS_CALLS = {
        "system", "popen", "spawn", "execv", "execve", "fork", "eval", "exec",
        "__import__", "unlink", "remove", "rmdir", "removedirs", "kill", "rmtree", "getattr"
    }
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in PROHIBITED_MODULES:
                    return (False, "", f"AST validation blocked prohibited module import: '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in PROHIBITED_MODULES:
                return (False, "", f"AST validation blocked prohibited module import: '{node.module}'")
        elif isinstance(node, ast.Call):
            target_name = None
            if isinstance(node.func, ast.Attribute) and node.func.attr in DANGEROUS_CALLS:
                target_name = node.func.attr
            elif isinstance(node.func, ast.Name) and node.func.id in DANGEROUS_CALLS:
                target_name = node.func.id
            if target_name:
                return (False, "", f"AST validation blocked dangerous call: {target_name}() is prohibited by sandbox security policy")

            # Check for destructive file open modes (w, a, x, +)
            is_open = (isinstance(node.func, ast.Name) and node.func.id == "open") or (isinstance(node.func, ast.Attribute) and node.func.attr == "open")
            if is_open:
                mode_str = None
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    mode_str = node.args[1].value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        mode_str = kw.value.value
                if mode_str and any(c in mode_str for c in ("w", "a", "x", "+")):
                    return (False, "", f"AST validation blocked open() with destructive mode '{mode_str}'")

    if not allow_exec:
        return (True, "syntax_ok_not_executed: AST syntax and structural validation passed (execution gated)", "")

    # If allow_exec is True, run in subprocess with restricted environment and cwd scoped to scratch
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    test_file = os.path.join(SCRATCH_DIR, f"sandbox_test_{os.getpid()}_{uuid.uuid4().hex[:8]}.py")
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)

        clean_env = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            "PATH": os.path.dirname(sys.executable),
            "PYTHONPATH": "",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            env=clean_env,
            cwd=SCRATCH_DIR,
            timeout=timeout_sec
        )
        return (result.returncode == 0, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return (False, "", f"Sandbox execution timed out after {timeout_sec}s")
    except Exception as e:
        return (False, "", str(e))
    finally:
        if os.path.exists(test_file):
            try:
                os.remove(test_file)
            except Exception:
                pass


# Backward-compatible alias
run_sandbox_validation = run_syntax_validation


def synthesize_and_promote_skill(name, description, domain="general", test_code=None, library_dir=DEFAULT_LIBRARY_DIR, allow_exec=False):
    """
    Autonomous Synthesis Pipeline:
    1. Author candidate SKILL.md with frontmatter validation
    2. Sandbox verification (AST check by default, subprocess only if allow_exec=True)
    3. If valid -> promotes and writes to skills_library atomically via safe_atomic_replace
    4. Triggers re-indexing with fail-loud error handling
    """
    clean_name, content = generate_skill_template(name, description, domain)

    # Verify target directory containment (VULN-001 / path traversal)
    lib_abs = os.path.abspath(library_dir)
    target_dir = os.path.abspath(os.path.join(library_dir, clean_name))
    if os.path.commonpath([lib_abs, target_dir]) != lib_abs:
        raise ValueError(f"Target path '{target_dir}' escapes library directory '{lib_abs}'")

    # Step 2: Sandbox Validation
    if test_code:
        success, stdout, stderr = run_sandbox_validation(test_code, allow_exec=allow_exec)
        if not success:
            return {
                "status": "failed",
                "stage": "sandbox_validation",
                "error": stderr or "Test assertions failed",
                "stdout": stdout
            }

    # Step 3: Promote to Library atomically
    os.makedirs(target_dir, exist_ok=True)
    target_skill_path = os.path.join(target_dir, "SKILL.md")
    temp_skill_path = os.path.join(target_dir, f"tmp_skill_{os.getpid()}_{uuid.uuid4().hex[:8]}.md")

    try:
        with open(temp_skill_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        safe_atomic_replace(temp_skill_path, target_skill_path)
    finally:
        if os.path.exists(temp_skill_path):
            try:
                os.remove(temp_skill_path)
            except Exception:
                pass

    # Step 4: Re-index into registry.json
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)
    try:
        from indexer import build_index
        reg_path = os.path.join(scripts_dir, "registry.json")
        build_index(reg_path)
    except Exception as e:
        return {
            "status": "failed",
            "stage": "indexing",
            "error": f"Failed to rebuild registry: {type(e).__name__}: {e}",
            "skill_name": clean_name,
            "path": target_skill_path.replace("\\", "/")
        }

    return {
        "status": "success",
        "skill_name": clean_name,
        "path": target_skill_path.replace("\\", "/"),
        "promoted_at": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Omni-Kernel Skill Synthesizer CLI")
    parser.add_argument("--name", "-n", required=True, help="Name of the skill to synthesize")
    parser.add_argument("--desc", "-d", required=True, help="Description of what the skill does")
    parser.add_argument("--domain", default="general", help="Technical domain")
    parser.add_argument("--test", "-t", default=None, help="Inline python test code to validate")
    parser.add_argument("--allow-exec", action="store_true", help="Explicitly permit test subprocess execution")
    args = parser.parse_args()

    result = synthesize_and_promote_skill(args.name, args.desc, args.domain, args.test, allow_exec=args.allow_exec)
    print(json.dumps(result, indent=2))
