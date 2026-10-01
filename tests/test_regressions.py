import contextlib
import copy
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import releases
import collector


def branch(version, url):
    return dict(version=version, status='prerelease', first='2026-10-01', eol='2031-10',
                firstEstimated=True, eolEstimated=True, manager='Manager', url=url,
                scheduleError=False, events=[])


def event(version, when, confirmed=False):
    return dict(version=version, date=when, kind='stable', url=releases.DOWNLOADS if confirmed else 'https://peps.python.org/pep-0790/', confirmed=confirmed)


def cached():
    current = branch('3.15', 'https://peps.python.org/pep-0790/')
    old = branch('2.6', 'https://peps.python.org/pep-0361/')
    current['events'] = [event('3.15.0', '2026-10-01'), event('3.15.1', '2026-12-01')]
    old['events'] = [event('2.6.1', '2008-12-01'), event('2.6.9', '2013-10-29', True)]
    return dict(schema=1, fetchedAt='2026-09-01T00:00:00+00:00', warnings=[], branches=[current, old])


class CollectionTests(unittest.TestCase):
    def collect(self, failures=(), parser_fail=False):
        previous = cached()
        original = copy.deepcopy(previous)
        def fetch(url):
            if url in failures:
                raise OSError('offline')
            return url
        def schedule(root, b):
            if parser_fail and b['version'] == '2.6':
                raise ValueError('bad date')
            return [event('3.15.0', '2026-10-08')] if b['version'] == '3.15' else []
        with patch('collector.fetch', side_effect=fetch), patch('collector.parse_branches', side_effect=lambda _: [dict(b, events=[]) for b in cached()['branches']]), patch('collector.parse_schedule', side_effect=schedule), patch('collector.parse_downloads', return_value=[event('3.15.2', '2026-09-28', True)]):
            result = collector.collect(previous)
        self.assertEqual(previous, original, 'Do not modify fallback data in memory')
        self.assertTrue(releases.validate_cache(result))
        return result

    def test_historical_failure_keeps_new_dates_and_only_failed_source(self):
        result = self.collect(['https://peps.python.org/pep-0361/'])
        current, old = result['branches']
        self.assertEqual(current['events'][1]['date'], '2026-10-08')
        self.assertNotIn('3.15.1', [e['version'] for e in current['events']], 'Do not retain removed future events from a successful source')
        self.assertEqual([e['version'] for e in old['events']], ['2.6.1'])
        self.assertTrue(old['scheduleError'])
        self.assertTrue(result['warnings'])

    def test_parser_failure_is_isolated(self):
        self.assertTrue(self.collect(parser_fail=True)['branches'][1]['scheduleError'])

    def test_archive_failure_preserves_confirmations_and_new_schedule(self):
        result = self.collect([releases.DOWNLOADS])
        self.assertEqual(result['branches'][0]['events'][0]['date'], '2026-10-08')
        self.assertTrue(result['branches'][1]['events'][0]['confirmed'])

    def test_guide_failure_still_updates_schedules(self):
        result = self.collect([collector.VERSIONS])
        self.assertEqual(result['branches'][0]['events'][1]['date'], '2026-10-08')
        self.assertTrue(result['warnings'])

    def test_total_outage_retains_original_timestamp(self):
        result = self.collect([collector.VERSIONS, releases.DOWNLOADS, 'https://peps.python.org/pep-0790/', 'https://peps.python.org/pep-0361/'])
        self.assertEqual(result['fetchedAt'], cached()['fetchedAt'])
        self.assertEqual(result['branches'][0]['events'], cached()['branches'][0]['events'])


class CacheTests(unittest.TestCase):
    def test_nested_invalid_cache_is_rejected(self):
        mutations = [lambda d: d['branches'][0].pop('events'),
                     lambda d: d['branches'][0].update(events=None),
                     lambda d: d['branches'][0]['events'][0].update(date='2026-02-30'),
                     lambda d: d['branches'][0]['events'][0].update(confirmed='false'),
                     lambda d: d.update(fetchedAt=None),
                     lambda d: d.update(warnings='oops'),
                     lambda d: d['branches'][0].update(first='2026-99')]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'releases.json'
            for mutate in mutations:
                value = cached()
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertIsNone(releases.read_cache(path), value)

    def test_invalid_cache_refetches_even_when_recent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'releases.json'
            path.write_text('{"schema":1,"branches":[{"version":"3.15"}]}')
            with patch('sys.argv', ['releases.py', '--cache-dir', directory]), patch('releases.fetch_feed', return_value=cached()) as collect, patch('builtins.print') as output:
                releases.main()
            collect.assert_called_once_with()
            self.assertEqual(json.loads(output.call_args.args[0])['branches'], cached()['branches'])
            self.assertEqual(releases.read_cache(path), cached())

    def test_invalid_cache_offline_returns_json_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'releases.json'
            path.write_text('{"schema":1,"branches":[{"version":"3.15"}]}')
            for args in (['--cached'], []):
                with patch('sys.argv', ['releases.py', '--cache-dir', directory] + args), patch('releases.fetch_feed', side_effect=OSError('offline')), patch('builtins.print') as output:
                    releases.main()
                self.assertEqual(json.loads(output.call_args.args[0])['branches'], [])


class InstallerTests(unittest.TestCase):
    def run_installer(self, fail_restart=False):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'omarchy'
            config.mkdir()
            data = {'version': 1, 'bar': {'layout': {'left': [{'id': 'frank.python-releases', 'favorite': '3.14'}], 'right': []}}}
            (config / 'shell.json').write_text(json.dumps(data))
            calls = []
            def run(command, **kwargs):
                calls.append(command)
                if fail_restart and command == ['omarchy', 'restart', 'shell']:
                    raise subprocess.CalledProcessError(1, command)
            output = io.StringIO()
            with patch.dict(os.environ, XDG_CONFIG_HOME=directory), patch('subprocess.run', side_effect=run), contextlib.redirect_stdout(output):
                if fail_restart:
                    with self.assertRaises(subprocess.CalledProcessError):
                        runpy.run_path(str(Path(__file__).resolve().parents[1] / 'install.py'))
                else:
                    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'install.py'))
            self.assertEqual(json.loads((config / 'shell.json').read_text()), data)
            return calls, output.getvalue()

    def test_install_restarts_after_enabling_and_preserves_settings(self):
        calls, output = self.run_installer()
        self.assertEqual(calls[-1], ['omarchy', 'restart', 'shell'])
        self.assertEqual(calls[-2], ['omarchy', 'plugin', 'enable', 'frank.python-releases'])
        self.assertIn('Installiert:', output)

    def test_failed_restart_does_not_report_success(self):
        _, output = self.run_installer(fail_restart=True)
        self.assertNotIn('Installiert:', output)
