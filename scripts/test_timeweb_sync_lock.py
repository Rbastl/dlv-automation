#!/usr/bin/env python3
"""Unit checks for the Timeweb publisher's read-only/lock safety contract."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parent / "timeweb_sync_from_github.sh"


class TimewebSyncLockTests(unittest.TestCase):
    def test_existing_lock_is_an_error_without_network_or_lock_removal(self):
        # Stub external publishing programs: the lock check must run first.
        with TemporaryDirectory() as root:
            home = Path(root)
            (home / "dlvautomation" / "public_html").mkdir(parents=True)
            lock = home / ".dlv-automation-publish-lock"
            lock.mkdir()
            binpath = home / "bin"
            binpath.mkdir()
            for prog in ("git", "rsync"):
                p = binpath / prog
                p.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
                p.chmod(0o755)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = str(binpath) + os.pathsep + env.get("PATH", "")
            out = subprocess.run(
                ["/bin/sh", str(SCRIPT)],
                text=True, capture_output=True, env=env, timeout=5, check=False
            )
            self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
            self.assertIn("publish lock exists", out.stderr)
            self.assertTrue(lock.is_dir(), "Publisher must never remove an unknown live lock")
            self.assertEqual(list((home / "dlvautomation" / "public_html").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
