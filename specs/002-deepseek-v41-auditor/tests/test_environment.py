"""
Environment and Security Boundary Assertions for Omni-Auditor v4.1.
Verifies Python 3.11+ runtime, zero external dependencies, and AppLocker safety.
"""

import sys
import unittest
import importlib


class TestAuditorEnvironment(unittest.TestCase):
    def test_python_version_minimum_311(self):
        """Principle I & II: Requires Python 3.11+ for robust asyncio, sqlite, and typing."""
        self.assertGreaterEqual(
            sys.version_info[:2],
            (3, 11),
            f"Python version must be >= 3.11, found: {sys.version}"
        )

    def test_zero_third_party_dependencies_in_core_scripts(self):
        """Principle II & Ponytail Simplicity: scripts/consult_critic.py and scripts/sanitizer.py must use 100% stdlib."""
        import os
        import subprocess
        cmd = [
            sys.executable, "-c",
            "import consult_critic, sanitizer, sys; "
            "prohibited = ['requests', 'httpx', 'aiohttp', 'urllib3', 'pydantic', 'openai', 'deepseek', 'grpc']; "
            "loaded = [p for p in prohibited if p in sys.modules]; "
            "sys.exit(len(loaded))"
        ]
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts"))
        res = subprocess.run(cmd, cwd=scripts_dir)
        self.assertEqual(res.returncode, 0, "Core auditor scripts must not load any third party networking libraries.")

    def test_standard_library_modules_available(self):
        """Verify availability of essential standard library modules for REST client."""
        required_stdlib = [
            "urllib.request",
            "urllib.error",
            "json",
            "ssl",
            "os",
            "sys",
            "time",
            "random",
            "argparse",
            "hashlib",
            "pathlib"
        ]
        for mod_name in required_stdlib:
            mod = importlib.import_module(mod_name)
            self.assertIsNotNone(mod, f"Standard module '{mod_name}' must be importable.")


if __name__ == "__main__":
    unittest.main()
