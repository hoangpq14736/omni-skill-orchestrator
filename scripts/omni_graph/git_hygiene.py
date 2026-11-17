"""Git Hygiene Manager for Omni-Graph. Ensures .omni/ is excluded from Git commits."""

import os
import shlex
import sys
from pathlib import Path
from typing import Union

def ensure_git_hygiene(workspace_root: Union[str, Path]) -> bool:
    """
    Guarantees that a .gitignore in workspace_root contains an entry for the
    Omni-Kernel workspace artifacts (".omni/").

    Returns:
        True  - the .gitignore was created or modified,
        False - it already contained the entry or an I/O error occurred.
    """
    root = Path(workspace_root)
    gitignore = root / ".gitignore"
    entry = ".omni/"

    def line_matches(line: str) -> bool:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return False
        return stripped in (entry, entry.rstrip("/"))

    try:
        if not gitignore.exists():
            gitignore.write_text(
                f"# Omni-Kernel workspace artifacts\n{entry}\n",
                encoding="utf-8",
            )
            return True

        lines = gitignore.read_text(encoding="utf-8").splitlines()
        if any(line_matches(l) for l in lines):
            return False

        with gitignore.open("a", encoding="utf-8") as f:
            f.write(f"\n# Omni-Kernel workspace artifacts\n{entry}\n")
        return True

    except OSError as exc:
        print(f"Warning: could not ensure git hygiene - {exc}", file=sys.stderr)
        return False


def ensure_git_hooks(workspace_root: Union[str, Path], omni_graph_script: Union[str, Path, None] = None) -> bool:
    """
    Ensures git hooks (post-commit, post-merge, post-checkout) are installed in the workspace
    to automatically update the omni graph.
    """
    if os.environ.get("OMNI_READ_ONLY") == "1":
        return False

    try:
        root = Path(workspace_root).resolve()
        if not (root / ".git").is_dir() or not (root / ".git" / "hooks").is_dir():
            return False

        if omni_graph_script is not None:
            script_path = Path(omni_graph_script).resolve()
        else:
            script_path = (Path(__file__).resolve().parent.parent / "omni_graph.py").resolve()

        if not script_path.is_file():
            return False

        quoted_script = shlex.quote(script_path.as_posix())
        quoted_root = shlex.quote(root.as_posix())

        hooks = ["post-commit", "post-merge", "post-checkout"]
        hooks_dir = root / ".git" / "hooks"
        updated_any = False

        for hook_name in hooks:
            hook_file = hooks_dir / hook_name
            
            # Prepare hook content body depending on hook type
            if hook_name == "post-checkout":
                command_body = (
                    'if [ "${3:-1}" = "1" ]; then\n'
                    '    OMNI_PY="$(command -v python3 || command -v python)"\n'
                    f'    if [ -n "$OMNI_PY" ]; then\n'
                    f'        "$OMNI_PY" -B {quoted_script} --workspace {quoted_root} --scan >/dev/null 2>&1 &\n'
                    '    fi\n'
                    'fi'
                )
            else:
                command_body = (
                    'OMNI_PY="$(command -v python3 || command -v python)"\n'
                    'if [ -n "$OMNI_PY" ]; then\n'
                    f'    "$OMNI_PY" -B {quoted_script} --workspace {quoted_root} --scan >/dev/null 2>&1 &\n'
                    'fi'
                )

            block = f"# OMNI-GRAPH-HOOK-START\n{command_body}\n# OMNI-GRAPH-HOOK-END\n"

            if hook_file.exists():
                content = hook_file.read_text(encoding="utf-8")
                if "# OMNI-GRAPH-HOOK-START" in content:
                    continue
                
                # Append to existing hook
                new_content = content if content.endswith("\n") else content + "\n"
                new_content += "\n" + block
                hook_file.write_text(new_content, encoding="utf-8")
                updated_any = True
            else:
                # Create new hook file
                new_content = "#!/bin/sh\n\n" + block
                hook_file.write_text(new_content, encoding="utf-8")
                updated_any = True

            # Ensure chmod +x (0o755)
            try:
                current_mode = hook_file.stat().st_mode
                hook_file.chmod(current_mode | 0o111)
            except OSError:
                pass

        return updated_any

    except OSError:
        return False
