#!/usr/bin/env python3
"""Hosted Python release feed, local cache and countdowns; standard library only."""
import argparse
from datetime import date, datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

DOWNLOADS = "https://www.python.org/downloads/"
TTL = 12 * 60 * 60


FEED_URL = "https://15r10nk.github.io/omarchy-python-releases/releases.json"
MAX_FEED_BYTES = 8_000_000


def fetch_feed(url=FEED_URL):
    """Download and validate the hosted feed before replacing any local data."""
    request = Request(url, headers={"User-Agent": "Omarchy-Python-Releases/1.5",
                                   "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        payload = response.read(MAX_FEED_BYTES + 1)
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("Release feed is too large")
    data = json.loads(payload)
    if not validate_cache(data):
        raise ValueError("Invalid release feed")
    return data


def present(data, today, mode="feature", error=""):
    upcoming = []
    for branch in data.get("branches", []):
        # First releases also exist in the developer guide if a PEP is unavailable.
        events = list(branch["events"])
        first_version = branch["version"] + ".0"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", branch["first"]) and not any(e["version"] == first_version for e in events):
            events.append(dict(version=first_version, date=branch["first"], kind="stable", url=branch["url"], confirmed=False))
        for event in events:
            if event["date"] < today.isoformat() or event["confirmed"] or event["kind"] == "development":
                continue
            if mode == "feature" and (event["kind"] != "stable" or event["version"] != first_version):
                continue
            if mode == "stable" and event["kind"] != "stable":
                continue
            upcoming.append(event)
    upcoming.sort(key=lambda e: (e["date"], e["version"]))
    next_event = dict(upcoming[0]) if upcoming else None
    if next_event:
        next_event["days"] = (date.fromisoformat(next_event["date"]) - today).days
    return dict(data, next=next_event, today=today.isoformat(), error=error)


def valid_date(value, partial=False):
    if not isinstance(value, str):
        return False
    if partial and value == "":
        return True
    if partial and re.fullmatch(r"\d{4}-\d{2}", value):
        value += "-01"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_cache(data):
    """Validate every field consumed by Python and QML before trusting a cache."""
    if not isinstance(data, dict) or data.get("schema") != 1:
        return False
    if not isinstance(data.get("fetchedAt"), str):
        return False
    try:
        if datetime.fromisoformat(data["fetchedAt"]).tzinfo is None:
            return False
    except ValueError:
        return False
    if not isinstance(data.get("warnings"), list) or not all(isinstance(w, str) for w in data["warnings"]):
        return False
    if not isinstance(data.get("branches"), list) or not data["branches"]:
        return False
    for branch in data["branches"]:
        if not isinstance(branch, dict):
            return False
        if not isinstance(branch.get("version"), str) or not re.fullmatch(r"\d+\.\d+", branch["version"]):
            return False
        if not all(isinstance(branch.get(k), str) for k in ("status", "manager", "url")):
            return False
        if branch["url"] and not valid_source_url(branch["url"]):
            return False
        if not all(isinstance(branch.get(k), bool) for k in ("firstEstimated", "eolEstimated", "scheduleError")):
            return False
        if not all(valid_date(branch.get(k), partial=True) for k in ("first", "eol")):
            return False
        if not isinstance(branch.get("events"), list):
            return False
        for event in branch["events"]:
            if not isinstance(event, dict):
                return False
            if not all(isinstance(event.get(k), str) for k in ("version", "url")):
                return False
            if not valid_source_url(event["url"]):
                return False
            if event.get("kind") not in ("stable", "alpha", "beta", "rc", "development"):
                return False
            if not isinstance(event.get("confirmed"), bool) or not valid_date(event.get("date")):
                return False
    return True


def valid_source_url(value):
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and url.netloc in
                ("www.python.org", "peps.python.org", "devguide.python.org"))
    except ValueError:
        return False


def read_cache(path):
    try:
        data = json.loads(path.read_text())
        return data if validate_cache(data) else None
    except (OSError, ValueError):
        return None


def write_cache(path, data):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--cached", action="store_true", help="Read only; never access the network")
    parser.add_argument("--mode", choices=["feature", "stable", "all"], default="feature")
    parser.add_argument("--cache-dir", type=Path, default=Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "omarchy-python-releases")
    args = parser.parse_args()
    path = args.cache_dir / "releases.json"
    failure_path = args.cache_dir / "failure.json"
    data, error = read_cache(path), ""
    if not args.cached:
        try:
            args.cache_dir.mkdir(parents=True, exist_ok=True)
            with (args.cache_dir / "refresh.lock").open("w") as lock:
                # Multiple monitors share a cache and serialize refreshes.
                fcntl.flock(lock, fcntl.LOCK_EX)
                data = read_cache(path)
                age = time.time() - path.stat().st_mtime if data else float("inf")
                try:
                    failure = json.loads(failure_path.read_text())
                    if not isinstance(failure, dict) or not isinstance(failure.get("time"), (int, float)) or not isinstance(failure.get("error"), str):
                        failure = {}
                except (OSError, ValueError):
                    failure = {}
                retry_later = time.time() - failure.get("time", 0) < 600 and not args.refresh
                if retry_later:
                    error = failure.get("error", "Aktualisierung fehlgeschlagen")
                elif (args.refresh and age > 10) or age > TTL or failure:
                    fresh = fetch_feed()
                    if not validate_cache(fresh):
                        raise ValueError("Ungültige Release-Daten")
                    data = fresh
                    write_cache(path, data)
                    # Source warnings belong to the feed; retry only failed downloads.
                    failure_path.unlink(missing_ok=True)
        except Exception as exc:
            error = "Aktualisierung fehlgeschlagen: " + str(exc)
            try:
                write_cache(failure_path, dict(time=time.time(), error=error))
            except OSError:
                pass
    if data is None:
        data = dict(schema=1, branches=[], fetchedAt="", warnings=[])
        error = error or "Noch keine gespeicherten Release-Daten"
    print(json.dumps(present(data, date.today(), args.mode, error), ensure_ascii=False))


if __name__ == "__main__":
    main()
