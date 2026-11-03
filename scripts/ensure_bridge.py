#!/usr/bin/env python3
"""
Ensure Argon Bridge is running in the background.
Uses Windows pythonw via Start-Process to ensure full decoupling from parent processes.
"""
import os
import subprocess
import sys
import urllib.request

def is_running():
    try:
        with urllib.request.urlopen("http://127.0.0.1:7890/health", timeout=0.6) as resp:
            return True
    except Exception:
        return False

def ensure():
    if is_running():
        sys.exit(0)

    bridge_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "argon_bridge.py")
    if os.path.exists(bridge_path):
        if sys.platform == "win32":
            cmd = f'Start-Process -FilePath "pythonw.exe" -ArgumentList \'"{bridge_path}"\''
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True)
        else:
            subprocess.Popen([sys.executable, bridge_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    ensure()
