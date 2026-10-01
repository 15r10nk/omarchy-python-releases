#!/usr/bin/env python3
"""Build a validated Pages artifact, using the published feed as fallback."""
import argparse
from pathlib import Path
import sys
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collector import collect
from releases import FEED_URL, fetch_feed, validate_cache, write_cache


def build(output, previous_url=FEED_URL):
    try:
        previous = fetch_feed(previous_url)
    except HTTPError as exc:
        if exc.code != 404:
            raise
        exc.close()
        previous = None  # First deployment only.
    fresh = collect(previous)
    if not validate_cache(fresh):
        raise ValueError("Collector produced an invalid feed")
    if previous and fresh["fetchedAt"] == previous["fetchedAt"]:
        raise ValueError("All sources failed; retaining the published feed")
    if previous is None and fresh["warnings"]:
        raise ValueError("First publication requires all sources to succeed")
    output.mkdir(parents=True, exist_ok=True)
    write_cache(output / "releases.json", fresh)
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<title>Python release feed</title><h1>Python release feed</h1>'
        '<p><a href="releases.json">Download releases.json</a></p>'
        '<p><a href="https://github.com/15r10nk/omarchy-python-releases">'
        'Source and documentation</a></p></html>\n')
    for warning in fresh["warnings"]:
        print(warning, file=sys.stderr)
    return fresh


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("_site"))
    parser.add_argument("--previous-url", default=FEED_URL)
    args = parser.parse_args()
    build(args.output, args.previous_url)
