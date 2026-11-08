"""
Backend Client and Inter-Process Mutex Module for Omni-Memory v4.1.
Provides atomic file locking with 30s stale recovery and socket liveness polling.
Cross-platform compatible (Windows and Unix) using 100% Python Standard Library.
"""

import os
import socket
import time
from typing import Optional


def acquire_lock_with_stale_recovery(lock_path: str, stale_timeout_sec: float = 30.0) -> bool:
    """
    Acquire inter-process file mutex with automatic stale-lock recovery.
    Cross-platform atomic implementation using os.O_CREAT | os.O_EXCL.
    """
    if os.path.exists(lock_path):
        try:
            file_age = time.time() - os.path.getmtime(lock_path)
            if file_age > stale_timeout_sec:
                # Forcefully recover stale lock
                try:
                    os.remove(lock_path)
                except OSError:
                    pass
        except OSError:
            pass

    try:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        fd = os.open(lock_path, flags)
        payload = f"pid={os.getpid()};time={time.time()}".encode("utf-8")
        os.write(fd, payload)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except OSError:
        return False


def acquire_autostart_lock(
    lock_path: str = "llama_autostart.lock",
    timeout_sec: float = 25.0,
    stale_sec: float = 30.0
) -> bool:
    """
    Poll to acquire autostart lock with retries up to timeout_sec.
    Returns True if acquired within budget, False otherwise.
    """
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if acquire_lock_with_stale_recovery(lock_path, stale_timeout_sec=stale_sec):
            return True
        time.sleep(0.2)
    return False


def release_autostart_lock(lock_path: str = "llama_autostart.lock") -> bool:
    """Safely release the file lock by removing the lock file."""
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
            return True
        return False
    except OSError:
        return False


def poll_socket_alive(host: str = "127.0.0.1", port: int = 8080, timeout_sec: float = 1.0) -> bool:
    """Check if the backend daemon is actively listening on target host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def is_local_worker_available(host: str = "127.0.0.1", port: int = 8080, timeout_sec: float = 0.5) -> bool:
    """Fast probe (<500ms) to check if local AMD MI50 server is active for execution routing."""
    return poll_socket_alive(host=host, port=port, timeout_sec=timeout_sec)
