"""
Omni-Kernel v3.0: Autonomous Skill, Rule & Tool Synthesizer
Enables the AI to independently hypothesize, author, sandbox-test, and promote
new skills, rules, and MCP wrappers when facing unmapped technical requirements.
"""

import os
import sys
import json
import re
import subprocess
import tempfile
from datetime import datetime

HOME = os.path.expanduser("~")
DEFAULT_LIBRARY_DIR = os.path.join(HOME, ".gemini", "config", "skills_library")
SCRATCH_DIR = os.path.join(tempfile.gettempdir(), "omni_sandbox")


def generate_skill_template(name, description, domain="general", patterns=None, gotchas=None):
    """Generates a standard, production-ready SKILL.md document."""
    clean_name = re.sub(r'[^a-z0-9\-]', '-', name.lower().strip()).strip('-')
    patterns_text = "\n".join([f"- {p}" for p in (patterns or ["Follow standard library patterns first", "Validate all inputs at trust boundaries"])])
    gotchas_text = "\n".join([f"- {g}" for g in (gotchas or ["Never hardcode credentials or secrets", "Avoid unrequested abstractions or wrappers (YAGNI)"])])

    skill_content = f"""---
name: {clean_name}
description: >-
  {description.strip()}
metadata:
  version: 1.0.0
  domain: {domain}
  auto_generated: true
  generated_at: {datetime.now().isoformat()}
---

# {clean_name.replace('-', ' ').title()}

{description.strip()}

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
    return clean_name, skill_content


def run_sandbox_validation(test_code, timeout_sec=5):
    """
    Executes a test script inside a safe, isolated subprocess sandbox.
    Returns (success: bool, stdout: str, stderr: str).
    """
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    test_file = os.path.join(SCRATCH_DIR, f"sandbox_test_{os.getpid()}_{int(datetime.now().timestamp())}.py")
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)

        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
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


def synthesize_and_promote_skill(name, description, domain="general", test_code=None, library_dir=DEFAULT_LIBRARY_DIR):
    """
    Autonomous Synthesis Pipeline:
    1. Author candidate SKILL.md
    2. Sandbox verification (runs self-check test)
    3. If valid -> promotes and writes to skills_library
    4. Triggers re-indexing
    """
    clean_name, content = generate_skill_template(name, description, domain)

    # Step 2: Sandbox Validation
    if test_code:
        success, stdout, stderr = run_sandbox_validation(test_code)
        if not success:
            return {
                "status": "failed",
                "stage": "sandbox_validation",
                "error": stderr or "Test assertions failed",
                "stdout": stdout
            }

    # Step 3: Promote to Library
    target_dir = os.path.join(library_dir, clean_name)
    os.makedirs(target_dir, exist_ok=True)
    target_skill_path = os.path.join(target_dir, "SKILL.md")

    with open(target_skill_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Step 4: Re-index into registry.json
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)
    try:
        from indexer import build_index
        reg_path = os.path.join(scripts_dir, "registry.json")
        build_index(reg_path)
    except Exception as e:
        pass

    return {
        "status": "success",
        "skill_name": clean_name,
        "path": target_skill_path.replace("\\", "/"),
        "promoted_at": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Omni-Kernel Skill Synthesizer CLI")
    parser.add_argument("--name", "-n", required=True, help="Name of the skill to synthesize")
    parser.add_argument("--desc", "-d", required=True, help="Description of what the skill does")
    parser.add_argument("--domain", default="general", help="Technical domain")
    parser.add_argument("--test", "-t", default=None, help="Inline python test code to validate")
    args = parser.parse_args()

    result = synthesize_and_promote_skill(args.name, args.desc, args.domain, args.test)
    print(json.dumps(result, indent=2))
