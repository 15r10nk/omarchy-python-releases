import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import releases
from scripts import build_feed
from test_regressions import cached


class FeedTests(unittest.TestCase):
    def test_download_validates_json_and_uses_only_feed_url(self):
        data = cached()
        with patch('releases.urlopen', return_value=io.BytesIO(json.dumps(data).encode())) as get:
            self.assertEqual(releases.fetch_feed(), data)
        self.assertEqual(get.call_args.args[0].full_url, releases.FEED_URL)

    def test_invalid_feed_keeps_existing_cache(self):
        for payload in (b'<html>Unavailable</html>', b'{"schema":2}',
                        b'x' * (releases.MAX_FEED_BYTES + 1)):
            with self.subTest(size=len(payload)), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'releases.json'
                releases.write_cache(path, cached())
                import os
                os.utime(path, (0, 0))
                with patch('sys.argv', ['releases.py', '--refresh', '--cache-dir', directory]), \
                     patch('releases.urlopen', return_value=io.BytesIO(payload)), patch('builtins.print') as out:
                    releases.main()
                self.assertEqual(releases.read_cache(path), cached())
                self.assertTrue(json.loads(out.call_args.args[0])['error'])

    def test_untrusted_links_and_naive_timestamps_rejected(self):
        for url in ('javascript:alert(1)', 'file:///etc/passwd', 'https://example.com/',
                    'https://www.python.org@evil.example/'):
            data = cached()
            data['branches'][0]['events'][0]['url'] = url
            self.assertFalse(releases.validate_cache(data))
        data = cached()
        data['fetchedAt'] = '2026-10-01T00:00:00'
        self.assertFalse(releases.validate_cache(data))

    def test_source_warnings_do_not_cause_download_retry_loop(self):
        data = cached()
        data['warnings'] = ['Source unavailable']
        with tempfile.TemporaryDirectory() as directory:
            with patch('sys.argv', ['releases.py', '--cache-dir', directory]), \
                 patch('releases.fetch_feed', return_value=data) as get, patch('builtins.print'):
                releases.main()
                releases.main()
            self.assertEqual(get.call_count, 1)
            self.assertFalse((Path(directory) / 'failure.json').exists())


class BuildTests(unittest.TestCase):
    def test_partial_failure_uses_previous_and_publishes_warnings(self):
        previous = cached()
        fresh = copy.deepcopy(previous)
        fresh.update(fetchedAt='2026-10-01T00:00:00+00:00', warnings=['Source unavailable'])
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(build_feed, 'fetch_feed', return_value=previous), \
                 patch.object(build_feed, 'collect', return_value=fresh) as collect:
                build_feed.build(Path(directory))
            collect.assert_called_once_with(previous)
            self.assertEqual(releases.read_cache(Path(directory) / 'releases.json'), fresh)

    def test_total_outage_does_not_write_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(build_feed, 'fetch_feed', return_value=cached()), \
                 patch.object(build_feed, 'collect', return_value=cached()):
                with self.assertRaisesRegex(ValueError, 'All sources failed'):
                    build_feed.build(Path(directory))
            self.assertFalse((Path(directory) / 'releases.json').exists())

    def test_first_deployment_requires_complete_collection(self):
        for warnings in ([], ['Source unavailable']):
            data = cached()
            data['warnings'] = warnings
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(build_feed, 'fetch_feed', side_effect=HTTPError(releases.FEED_URL, 404, '', {}, None)), \
                     patch.object(build_feed, 'collect', return_value=data):
                    if warnings:
                        with self.assertRaises(ValueError):
                            build_feed.build(Path(directory))
                    else:
                        build_feed.build(Path(directory))
                        self.assertEqual(releases.read_cache(Path(directory) / 'releases.json'), data)

    def test_unavailable_previous_feed_aborts_collection(self):
        with patch.object(build_feed, 'fetch_feed', side_effect=OSError('offline')), \
             patch.object(build_feed, 'collect') as collect:
            with self.assertRaises(OSError):
                build_feed.build(Path('/unused'))
            collect.assert_not_called()
