"""Git Hygiene Manager for Omni-Graph. Ensures .omni/ is excluded from Git commits."""

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
