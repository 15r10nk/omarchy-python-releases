#!/usr/bin/env python3
"""Official Python release data; standard library only, with a disk cache."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import fcntl
import gzip
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.request import Request, urlopen

VERSIONS = "https://devguide.python.org/versions/"
DOWNLOADS = "https://www.python.org/downloads/"
TTL = 12 * 60 * 60


class Node:
    def __init__(self, tag="", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return " ".join(c.text() if isinstance(c, Node) else c for c in self.children).strip()

    def find(self, tag):
        for child in self.children:
            if isinstance(child, Node):
                if child.tag == tag:
                    yield child
                yield from child.find(tag)


class Document(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def fetch(url):
    request = Request(url, headers={"User-Agent": "Omarchy-Python-Releases/1.0", "Accept-Encoding": "identity"})
    with urlopen(request, timeout=15) as response:
        data = response.read(8_000_001)
        if len(data) > 8_000_000:
            raise ValueError("Antwort zu groß")
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return Document(data.decode("utf-8")).root


def parse_branches(root):
    branches = []
    main_version = re.search(r"future Python\s+(\d+\.\d+)", root.text())
    for row in root.find("tr"):
        cells = [c for c in row.children if isinstance(c, Node) and c.tag == "td"]
        if len(cells) != 6:
            continue
        version, _, status, first, eol, manager = [re.sub(r"\s+", " ", c.text()) for c in cells]
        if version == "main" and main_version:
            version = main_version[1]
        if not re.fullmatch(r"\d+\.\d+", version):
            continue
        links = [a.attrs.get("href", "") for a in cells[1].find("a")]
        schedule = next((u for u in links if re.fullmatch(r"https://peps\.python\.org/pep-\d+/", u)), "")
        branches.append(dict(version=version, status=status, first=first, eol=eol,
                             eolEstimated=bool(list(cells[4].find("em"))),
                             firstEstimated=bool(list(cells[3].find("em"))),
                             manager=manager, url=schedule, events=[]))
    if not branches or not any(b["status"] == "prerelease" or b["status"] == "feature" for b in branches):
        raise ValueError("Python-Versionstabelle konnte nicht gelesen werden")
    return branches


MONTHS = {name: i for i, name in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(text):
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        return date.fromisoformat(match[1]).isoformat()
    match = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b", text)
    if match and match[1][:3].lower() in MONTHS:
        return date(int(match[3]), MONTHS[match[1][:3].lower()], int(match[2])).isoformat()
    return ""


def parse_schedule(root, branch):
    events = {}
    for item in root.find("li"):
        if list(item.find("li")):
            continue
        text = re.sub(r"\s+", " ", item.text())
        match = re.match(r"(?:Python\s+)?(" + re.escape(branch["version"]) + r"(?:\.\d+)?)(.*?)(?::|\s[-–]\s)\s*(.*)", text)
        if not match or re.search(r"cancel|skip|withdraw", text, re.I):
            continue
        when = parse_date(match[3])
        if not when:
            continue
        base, suffix = match[1], match[2].strip()
        phase = re.search(r"(?:alpha|beta|candidate|rc|a|b)\s*(\d+)", suffix, re.I)
        if phase:
            kind = "alpha" if re.match(r"alpha|a\d", suffix, re.I) else "beta" if re.match(r"beta|b\d", suffix, re.I) else "rc"
            label = base + {"alpha": "a", "beta": "b", "rc": "rc"}[kind] + phase[1]
        elif "development" in suffix.lower():
            kind, label = "development", base + " Entwicklung"
        elif suffix.lower() in ("", "final", "release", "final release"):
            kind, label = "stable", base
        else:
            continue
        events[(label, when)] = dict(version=label, date=when, kind=kind, url=branch["url"], confirmed=False)
    return list(events.values())


def parse_downloads(root):
    releases = []
    for item in root.find("li"):
        spans = {s.attrs.get("class"): s for s in item.find("span")}
        number, released = spans.get("release-number"), spans.get("release-date")
        if not number or not released or list(item.find("li")):
            continue
        match = re.fullmatch(r"Python\s+(\d+\.\d+(?:\.\d+)?(?:(?:a|b|rc)\d+)?)", number.text())
        when = parse_date(released.text())
        if not match or not when:
            continue
        link = next(number.find("a"), None)
        path = link.attrs.get("href", "") if link else ""
        kind = "alpha" if re.search(r"a\d+$", match[1]) else "beta" if re.search(r"b\d+$", match[1]) else "rc" if "rc" in match[1] else "stable"
        releases.append(dict(version=match[1], date=when, kind=kind,
                             url="https://www.python.org" + path if path.startswith("/downloads/") else DOWNLOADS,
                             confirmed=True))
    if not releases:
        raise ValueError("Python-Releasearchiv konnte nicht gelesen werden")
    return releases


def collect(previous=None):
    previous = previous or {"branches": []}
    old = {b["version"]: b for b in previous["branches"]}
    warnings = []
    successful_sources = 0
    try:
        branches = parse_branches(fetch(VERSIONS))
        successful_sources += 1
    except Exception:
        if not old:
            raise
        warnings.append("Versionstabelle nicht erreichbar – gespeicherte Metadaten")
        branches = [dict(b, events=[]) for b in old.values()]
    urls = sorted({b["url"] for b in branches if b["url"] and b["url"] != DOWNLOADS})

    def get(url):
        try:
            return url, fetch(url)
        except Exception:
            return url, None

    with ThreadPoolExecutor(max_workers=6) as executor:
        pages = dict(executor.map(get, urls + [DOWNLOADS]))
    for branch in branches:
        cached = old.get(branch["version"], {})
        branch["scheduleError"] = False
        branch["events"] = []
        if not branch["url"] or branch["url"] == DOWNLOADS:
            continue
        try:
            root = pages.get(branch["url"])
            if root is None:
                raise ValueError("Releaseplan nicht erreichbar")
            branch["events"] = parse_schedule(root, branch)
            successful_sources += 1
        except Exception:
            branch["scheduleError"] = True
            branch["events"] = [dict(e) for e in cached.get("events", []) if not e["confirmed"]]
            warnings.append("Releaseplan " + branch["version"] + " nicht erreichbar – gespeicherte Termine")
    try:
        if pages[DOWNLOADS] is None:
            raise ValueError("Releasearchiv nicht erreichbar")
        archive = parse_downloads(pages[DOWNLOADS])
        successful_sources += 1
    except Exception:
        warnings.append("Releasearchiv nicht erreichbar – gespeicherte Veröffentlichungen")
        archive = [dict(e) for b in old.values() for e in b["events"] if e["confirmed"]]
    for event in archive:
        version = ".".join(event["version"].split(".")[:2])
        branch = next((b for b in branches if b["version"] == version), None)
        if branch is None:
            branch = dict(version=version, status="end-of-life", first="", eol="",
                          eolEstimated=False, firstEstimated=False, manager="", url=DOWNLOADS,
                          events=[], scheduleError=False)
            branches.append(branch)
        branch["events"] = [e for e in branch["events"] if e["version"] != event["version"]]
        branch["events"].append(dict(event))
    for branch in branches:
        branch["events"].sort(key=lambda e: (e["date"], e["version"]))
    branches.sort(key=lambda b: tuple(map(int, b["version"].split("."))), reverse=True)
    fetched_at = datetime.now(timezone.utc).isoformat() if successful_sources else previous["fetchedAt"]
    return dict(schema=1, fetchedAt=fetched_at, branches=branches, warnings=warnings)


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
        datetime.fromisoformat(data["fetchedAt"])
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
            if event.get("kind") not in ("stable", "alpha", "beta", "rc", "development"):
                return False
            if not isinstance(event.get("confirmed"), bool) or not valid_date(event.get("date")):
                return False
    return True


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
                    fresh = collect(data)
                    if not validate_cache(fresh):
                        raise ValueError("Ungültige Release-Daten")
                    data = fresh
                    write_cache(path, data)
                    if fresh["warnings"]:
                        error = "; ".join(fresh["warnings"])
                    if error:
                        write_cache(failure_path, dict(time=time.time(), error=error))
                    else:
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
