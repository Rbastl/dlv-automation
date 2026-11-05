#!/usr/bin/env python3
"""Public competitor baseline cache tests: no network and no user data."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import seo_monitor


class CompetitorBaselineTests(unittest.TestCase):
    def test_prefers_restored_public_cache(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                target = Path("seo-history/competitors.json")
                target.parent.mkdir(parents=True)
                rows = [{"url": "https://example.org/page", "status": "ok",
                         "title": "Old title", "h1": "Guide", "description": "Public"}]
                target.write_text(json.dumps({"pages": rows}), encoding="utf-8")
                with patch.dict(os.environ, {"GH_TOKEN": "", "GITHUB_REPOSITORY": ""}):
                    result = seo_monitor.previous_public_snapshot()
                self.assertEqual(result["https://example.org/page"]["title"], "Old title")
            finally:
                os.chdir(old)

    def test_missing_cache_no_auth_returns_empty_without_network(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as root:
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"GH_TOKEN": "", "GITHUB_REPOSITORY": ""}):
                    self.assertEqual(seo_monitor.previous_public_snapshot(), {})
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
