#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Windows Service & Task Scheduler Manager for Consolidator Daemon
Provides non-admin user-level persistence via Windows Task Scheduler (schtasks.exe).
Runs quietly in background using pythonw.exe without console popups or terminal dependency.
Zero external dependencies, 100% Python Standard Library.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

TASK_NAME = "OmniKernelConsolidator"
_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent
_CONSOLIDATOR_PATH = _CURRENT_DIR / "consolidator.py"


def _run_cmd(cmd: list) -> tuple:
    """Execute command silently without window creation."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=flags
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _find_pythonw() -> Path:
    """Locate pythonw.exe for silent non-window background execution."""
    exe_dir = Path(sys.executable).parent
    candidate = exe_dir / "pythonw.exe"
    if candidate.is_file():
        return candidate
    return Path(sys.executable)


def install_task(interval_minutes: int = 15) -> bool:
    """Register the Windows Scheduled Task to run out-of-band consolidation."""
    if os.name != "nt":
        sys.stderr.write("[!] Error: Task Scheduler is only available on Windows.\n")
        return False

    py_exe = _find_pythonw()
    if not _CONSOLIDATOR_PATH.is_file():
        sys.stderr.write(f"[!] Error: Consolidator not found at {_CONSOLIDATOR_PATH}\n")
        return False

    task_cmd = f'"{py_exe}" "{_CONSOLIDATOR_PATH}" --workspace "{_PROJECT_ROOT}" --batch-run'
    schtasks_cmd = [
        "schtasks",
        "/Create",
        "/SC", "MINUTE",
        "/MO", str(interval_minutes),
        "/TN", TASK_NAME,
        "/TR", task_cmd,
        "/F"
    ]

    rc, out, err = _run_cmd(schtasks_cmd)
    if rc == 0:
        print(f"✔ Successfully installed Windows Scheduled Task '{TASK_NAME}' (Interval: {interval_minutes}m).")
        print(f"  • Runner: {py_exe}")
        print(f"  • Target: {_CONSOLIDATOR_PATH}")
        print(f"  • Workspace: {_PROJECT_ROOT}")
        return True
    else:
        sys.stderr.write(f"[!] Failed to install scheduled task: {err or out}\n")
        return False


def get_task_status() -> dict:
    """Query Task Scheduler for execution status and next run time."""
    if os.name != "nt":
        return {"status": "unsupported_os"}

    rc, out, err = _run_cmd(["schtasks", "/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"])
    if rc != 0:
        return {"status": "not_installed", "error": err or out}

    info = {"status": "installed"}
    for line in out.splitlines():
        if ":" in line:
            parts = line.split(":", 1)
            k = parts[0].strip()
            v = parts[1].strip()
            if k in ("Status", "Next Run Time", "Last Run Time", "Last Result", "TaskName"):
                info[k.lower().replace(" ", "_")] = v
    return info


def uninstall_task() -> bool:
    """Remove the Windows Scheduled Task cleanly."""
    if os.name != "nt":
        return False

    rc, out, err = _run_cmd(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    if rc == 0:
        print(f"✔ Successfully removed Windows Scheduled Task '{TASK_NAME}'.")
        return True
    else:
        sys.stderr.write(f"[!] Failed to remove task '{TASK_NAME}': {err or out}\n")
        return False


def run_now() -> bool:
    """Trigger immediate execution of the consolidator."""
    if os.name != "nt":
        return False

    # Try triggering via Task Scheduler first
    rc, out, err = _run_cmd(["schtasks", "/Run", "/TN", TASK_NAME])
    if rc == 0:
        print(f"✔ Triggered '{TASK_NAME}' via Windows Task Scheduler.")
        return True

    # Fallback to direct Python subprocess
    py_exe = _find_pythonw()
    rc, out, err = _run_cmd([str(py_exe), str(_CONSOLIDATOR_PATH), "--workspace", str(_PROJECT_ROOT), "--batch-run"])
    if rc == 0:
        print(f"✔ Executed consolidator directly ({out}).")
        return True
    else:
        sys.stderr.write(f"[!] Execution failed: {err or out}\n")
        return False


def check_or_heal_task(interval_minutes: int = 15) -> dict:
    """Verify task exists and is Ready. If missing or broken, auto-reinstalls."""
    status = get_task_status()
    if status.get("status") != "Ready":
        print(f"[*] Task '{TASK_NAME}' status is '{status.get('status')}'. Auto-healing...")
        install_task(interval_minutes=interval_minutes)
        return get_task_status()
    print(f"✔ Task '{TASK_NAME}' is healthy (Status: Ready).")
    return status


def main():
    parser = argparse.ArgumentParser(description="Omni-Kernel Windows Service & Task Scheduler Manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true", help="Install Windows Scheduled Task (15m interval)")
    group.add_argument("--status", action="store_true", help="Query task scheduler status")
    group.add_argument("--uninstall", action="store_true", help="Uninstall scheduled task")
    group.add_argument("--run-now", action="store_true", help="Trigger immediate consolidation run")
    group.add_argument("--self-heal", action="store_true", help="Verify task health and auto-reinstall if missing/broken")
    parser.add_argument("--interval", type=int, default=15, help="Schedule interval in minutes (default: 15)")

    args = parser.parse_args()

    if args.install:
        install_task(interval_minutes=args.interval)
    elif args.status:
        import json
        st = get_task_status()
        print(json.dumps(st, indent=2))
    elif args.uninstall:
        uninstall_task()
    elif args.run_now:
        run_now()
    elif args.self_heal:
        import json
        st = check_or_heal_task(interval_minutes=args.interval)
        print(json.dumps(st, indent=2))


if __name__ == "__main__":
    main()
