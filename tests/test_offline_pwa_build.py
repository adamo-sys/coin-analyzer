"""Build only public application assets, never workspace or collection material."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OfflinePwaBuildTests(unittest.TestCase):
    def test_build_is_closed_and_content_addressed(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "shell"
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/build_offline_pwa.py"), str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            inventory = json.loads((output / "shell.json").read_text())
            self.assertEqual(
                {p.name for p in output.iterdir()},
                {
                    "index.html",
                    "app.js",
                    "storage.js",
                    "media.js",
                    "style.css",
                    "manifest.webmanifest",
                    "icon-192.png",
                    "icon-512.png",
                    "sw.js",
                    "shell.json",
                },
            )
            for asset in inventory["assets"]:
                self.assertEqual(
                    hashlib.sha256((output / asset["path"]).read_bytes()).hexdigest(),
                    asset["sha256"],
                )
            worker = (output / "sw.js").read_text()
            self.assertIn(inventory["version"], worker)
            self.assertNotIn("__SHELL_MANIFEST__", worker)
            again = subprocess.run(
                [sys.executable, str(ROOT / "tools/build_offline_pwa.py"), str(output)],
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(
                again.returncode, 0, "Must not overwrite an existing artifact"
            )
