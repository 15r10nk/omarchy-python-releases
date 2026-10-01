import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import releases
import collector


class ReleasesTest(unittest.TestCase):
    def branch(self):
        return dict(version="3.15", first="2026-10-01", url="https://peps.python.org/pep-0790/", events=[], status="prerelease", manager="Manager", eol="2031-10", firstEstimated=True, eolEstimated=True, scheduleError=False)

    def event(self, version="3.15.0", when="2026-10-01", kind="stable", confirmed=False):
        return dict(version=version, date=when, kind=kind, confirmed=confirmed)

    def test_countdown_today_and_rollover(self):
        data = dict(branches=[self.branch()])
        self.assertEqual(releases.present(data, date(2026, 9, 26))["next"]["days"], 5)
        self.assertEqual(releases.present(data, date(2026, 10, 1))["next"]["days"], 0)
        self.assertIsNone(releases.present(data, date(2026, 10, 2))["next"])

    def test_modes_and_confirmed_release(self):
        branch = self.branch()
        branch["events"] = [self.event("3.15.0rc2", "2026-09-27", "rc"), self.event("3.15.1", "2026-09-28"), self.event()]
        data = dict(branches=[branch])
        today = date(2026, 9, 26)
        self.assertEqual(releases.present(data, today, "feature")["next"]["version"], "3.15.0")
        self.assertEqual(releases.present(data, today, "stable")["next"]["version"], "3.15.1")
        self.assertEqual(releases.present(data, today, "all")["next"]["version"], "3.15.0rc2")
        branch["events"][-1]["confirmed"] = True
        self.assertIsNone(releases.present(data, today, "feature")["next"])

    def test_pep_date_takes_precedence(self):
        branch = self.branch()
        branch["events"] = [self.event(when="2026-10-02")]
        self.assertEqual(releases.present(dict(branches=[branch]), date(2026, 9, 26))["next"]["days"], 6)

    def test_calendar_days_across_dst(self):
        branch = self.branch()
        branch["first"] = "2026-10-26"
        self.assertEqual(releases.present(dict(branches=[branch]), date(2026, 10, 24))["next"]["days"], 2)

    def test_schedule_stages_and_cancelled(self):
        root = collector.Document('''<ul>
          <li>3.15 development begins: Wednesday, 2025-05-07</li>
          <li>3.15.0 alpha 1: Tuesday, 2025-10-14</li>
          <li>3.15.0 beta 1: Thursday, 2026-05-07 (Feature freeze)</li>
          <li>3.15.0 candidate 2: Tuesday, 2026-09-01</li>
          <li>3.15.0 candidate 3: 2026-09-20 (cancelled)</li>
          <li>3.15.0 final: Thursday, 2026-10-01</li>
          <li>3.14.9: 2026-12-01</li></ul>''').root
        events = collector.parse_schedule(root, self.branch())
        self.assertEqual([e["kind"] for e in events], ["development", "alpha", "beta", "rc", "stable"])
        self.assertEqual(events[3]["version"], "3.15.0rc2")

    def test_branch_precision_and_dynamic_main(self):
        root = collector.Document('''<p>The main branch is currently the future Python 3.16</p><table>
          <tr><td>main</td><td><a href="https://peps.python.org/pep-0826/">PEP 826</a></td>
          <td>feature</td><td><em>2027-10-06</em></td><td><em>2032-10</em></td><td>Manager</td></tr></table>''').root
        b = collector.parse_branches(root)[0]
        self.assertEqual(b["version"], "3.16")
        self.assertEqual(b["eol"], "2032-10")
        self.assertTrue(b["eolEstimated"])

    def test_download_date_and_link(self):
        root = collector.Document('''<ol><li><span class="release-number"><a href="/downloads/release/python-3147/">Python 3.14.7</a></span>
          <span class="release-date">Aug. 5, 2026</span></li></ol>''').root
        event = collector.parse_downloads(root)[0]
        self.assertEqual(event["date"], "2026-08-05")
        self.assertTrue(event["confirmed"])
        self.assertEqual(event["url"], "https://www.python.org/downloads/release/python-3147/")

    def test_cache_corruption_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "releases.json"
            path.write_text("broken")
            self.assertIsNone(releases.read_cache(path))
            data = dict(schema=1, branches=[self.branch()], fetchedAt="2026-09-01T00:00:00+00:00", warnings=[])
            releases.write_cache(path, data)
            self.assertEqual(releases.read_cache(path), data)

    def test_offline_keeps_cache_and_backs_off(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "releases.json"
            data = dict(schema=1, branches=[self.branch()], fetchedAt="2026-09-01T00:00:00+00:00", warnings=[])
            releases.write_cache(path, data)
            import os
            os.utime(path, (0, 0))
            with patch("sys.argv", ["releases.py", "--cache-dir", directory]), patch("releases.fetch_feed", side_effect=OSError("offline")) as fetch, patch("builtins.print") as out:
                releases.main()
                first = json.loads(out.call_args.args[0])
                self.assertEqual(first["branches"], data["branches"])
                self.assertIn("offline", first["error"])
                releases.main()
                self.assertEqual(fetch.call_count, 1)
            self.assertEqual(releases.read_cache(path), data)

    def test_partial_refresh_updates_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "releases.json"
            data = dict(schema=1, branches=[self.branch()], fetchedAt="2026-09-01T00:00:00+00:00", warnings=[])
            releases.write_cache(path, data)
            import os
            os.utime(path, (0, 0))
            fresh = copy.deepcopy(data)
            fresh.update(fetchedAt="2026-09-28T00:00:00+00:00", warnings=["Releaseplan nicht erreichbar"])
            with patch("sys.argv", ["releases.py", "--cache-dir", directory]), patch("releases.fetch_feed", return_value=fresh), patch("builtins.print") as out:
                releases.main()
                self.assertEqual(json.loads(out.call_args.args[0])["fetchedAt"], fresh["fetchedAt"])
            self.assertEqual(releases.read_cache(path), fresh)


if __name__ == "__main__":
    unittest.main()
