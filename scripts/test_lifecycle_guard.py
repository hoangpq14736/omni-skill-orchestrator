#!/usr/bin/env python3
"""
Unit test suite for LifecycleGuard.
Validates atomic locking, auto-healing of stale locks, process liveness check,
and parent process termination detection.
"""

import os
import sys
import time
import json
import tempfile
import shutil
import subprocess

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from lifecycle_guard import LifecycleGuard


def test_liveness_detection():
    my_pid = os.getpid()
    assert LifecycleGuard.is_process_alive(my_pid) is True, "Current process must be alive"
    assert LifecycleGuard.is_process_alive(-1) is False, "Negative PID must be false"
    assert LifecycleGuard.is_process_alive(0) is False, "PID 0 must be false"
    assert LifecycleGuard.is_process_alive(9999999) is False, "Non-existent PID must be false"
    print("✔ Process liveness detection verified.")


def test_atomic_lock_and_single_instance():
    temp_dir = tempfile.mkdtemp()
    try:
        guard1 = LifecycleGuard(name="test_worker", lock_dir=temp_dir)
        guard2 = LifecycleGuard(name="test_worker", lock_dir=temp_dir)

        # First instance acquires lock
        assert guard1.acquire_lock() is True, "First instance must acquire lock"

        # Second instance must fail
        assert guard2.acquire_lock() is False, "Second instance must be rejected"

        # Release lock from instance 1
        guard1.release_lock()

        # Now instance 2 can acquire lock
        assert guard2.acquire_lock() is True, "Instance 2 must acquire lock after release"
        guard2.release_lock()
        print("✔ Atomic lock and single instance exclusion verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_auto_healing_stale_lock():
    temp_dir = tempfile.mkdtemp()
    try:
        lock_file = os.path.join(temp_dir, "test_stale.pid")
        # Simulate a dead process crash: write a non-existent PID
        with open(lock_file, "w", encoding="utf-8") as f:
            json.dump({"pid": 9999999, "name": "test_stale", "started_at": time.time() - 100}, f)

        guard = LifecycleGuard(name="test_stale", lock_dir=temp_dir)
        # Should auto-detect that PID 9999999 is dead and reclaim the lock
        assert guard.acquire_lock() is True, "Guard must auto-heal and reclaim lock from dead PID"
        guard.release_lock()
        print("✔ Auto-healing of stale lock verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_parent_watcher_subkill():
    """
    Spawns a child process that spawns a grandchild running start_parent_watcher.
    Kills the child process and verifies the grandchild exits immediately.
    """
    temp_dir = tempfile.mkdtemp()
    child_script = os.path.join(temp_dir, "child.py")
    grandchild_script = os.path.join(temp_dir, "grandchild.py")
    gc_flag = os.path.join(temp_dir, "grandchild_alive.txt")

    # Grandchild script: monitors parent and touches gc_flag
    with open(grandchild_script, "w", encoding="utf-8") as f:
        f.write(f"""
import sys, os, time
sys.path.insert(0, r"{_SCRIPT_DIR}")
from lifecycle_guard import LifecycleGuard

guard = LifecycleGuard("grandchild", lock_dir=r"{temp_dir}")
guard.start_parent_watcher(poll_interval=0.1)

flag_file = r"{gc_flag}"
while True:
    with open(flag_file, "w") as f:
        f.write(str(time.time()))
    time.sleep(0.1)
""")

    # Child script: spawns grandchild and sleeps
    with open(child_script, "w", encoding="utf-8") as f:
        f.write(f"""
import subprocess, sys, time
p = subprocess.Popen([sys.executable, r"{grandchild_script}"])
print("GRANDCHILD_PID:", p.pid, flush=True)
time.sleep(10)
""")

    try:
        child_proc = subprocess.Popen(
            [sys.executable, child_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Read grandchild PID
        first_line = child_proc.stdout.readline()
        assert "GRANDCHILD_PID:" in first_line
        gc_pid = int(first_line.split(":")[1].strip())

        # Wait until grandchild is running
        time.sleep(0.5)
        assert LifecycleGuard.is_process_alive(gc_pid) is True, "Grandchild must be alive"

        # Now KILL the child process (simulating IDE Force Kill / Crash)
        child_proc.kill()
        child_proc.wait()

        # Grandchild should detect parent termination within ~0.5s and self-terminate
        terminated = False
        for _ in range(20):
            time.sleep(0.1)
            if not LifecycleGuard.is_process_alive(gc_pid):
                terminated = True
                break

        assert terminated is True, "Grandchild must self-terminate upon parent kill"
        print("✔ Parent process watcher kill detection verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_liveness_detection()
    test_atomic_lock_and_single_instance()
    test_auto_healing_stale_lock()
    test_parent_watcher_subkill()
    print("✔ All LifecycleGuard tests PASSED successfully!")
