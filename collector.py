#!/usr/bin/env python3
"""Collect official Python release sources for the published JSON feed."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import gzip
from html.parser import HTMLParser
import re
from urllib.request import Request, urlopen

from releases import DOWNLOADS

VERSIONS = "https://devguide.python.org/versions/"


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
            if not branch["events"] and cached.get("events"):
                raise ValueError("Established release schedule unexpectedly empty")
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


