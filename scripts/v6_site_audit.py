#!/usr/bin/env python3
"""DLV V6 checks: all static pages, links, metadata, and responsive shell contracts."""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(".")
EXCLUDED = {"site-dist", "node_modules", ".git", ".venv"}
SHELL_EXCEPTIONS = {"index.html", "en/index.html", "razrabotka-scada/index.html", "en/scada-hmi-development/index.html"}

class Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = Counter()
        self.ids = []
        self.hrefs = []
        self.robots = None
        self.canonical = []
        self.stylesheets = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags[tag] += 1
        if "id" in a: self.ids.append(a["id"])
        if tag == "a" and "href" in a: self.hrefs.append(a["href"])
        if tag == "meta" and a.get("name", "").lower() == "robots": self.robots = a.get("content")
        if tag == "link":
            if a.get("rel") == "canonical": self.canonical.append(a.get("href"))
            if a.get("rel") == "stylesheet": self.stylesheets.append(a.get("href"))

def local_path(href):
    if not href.startswith("/"): return None
    p = urlsplit(href)
    path = unquote(p.path)
    if not path or path == "/": return Path("index.html")
    loc = Path(path.lstrip("/"))
    if path.endswith("/") or not loc.suffix: return loc / "index.html"
    return loc

def main():
    paths = sorted(p for p in ROOT.rglob("index.html") if not any(k in EXCLUDED for k in p.parts))
    if len(paths) != 50: raise AssertionError(f"Expected 50 HTML entry files, got {len(paths)}")
    data = {}
    for p in paths:
        parser = Tags()
        content = p.read_text(encoding="utf-8")
        parser.feed(content)
        if parser.tags["h1"] != 1: raise AssertionError(f"{p}: expected one H1, got {parser.tags['h1']}")
        repeated = [x for x, n in Counter(parser.ids).items() if n > 1]
        if repeated: raise AssertionError(f"{p}: repeated HTML IDs {repeated}")
        data[p.as_posix()] = (parser, content)
        if p.as_posix() not in SHELL_EXCEPTIONS:
            assert 'class="dlv-site-header"' in content, f"{p}: shared header absent"
            assert 'class="dlv-site-footer"' in content, f"{p}: shared footer absent"
            assert '/assets/dlv-v6-unified.css' in parser.stylesheets, f"{p}: shared stylesheet absent"
        for stylesheet in parser.stylesheets:
            if stylesheet and stylesheet.startswith("/") and not (ROOT / stylesheet.lstrip("/")).is_file():
                raise AssertionError(f"{p}: missing stylesheet {stylesheet}")
    found = 0
    for file, (doc, content) in data.items():
        for href in doc.hrefs:
            loc = local_path(href)
            if loc is None:
                if href.startswith("#"):
                    frag = unquote(urlsplit(href).fragment)
                    if frag and frag not in doc.ids:
                        raise AssertionError(f"{file}: missing own anchor #{frag}")
                continue
            if not (ROOT / loc).is_file():
                raise AssertionError(f"{file}: broken internal link {href} -> {loc}")
            fragment = unquote(urlsplit(href).fragment)
            if fragment and loc.as_posix() in data:
                ids = data[loc.as_posix()][0].ids
                if fragment not in ids:
                    raise AssertionError(f"{file}: target anchor {href} is missing")
            found += 1
    sitemap = ET.parse("sitemap.xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [e.text for e in sitemap.findall(".//s:url/s:loc", ns)]
    if len(urls) != 48 or len(urls) != len(set(urls)):
        raise AssertionError(f"Sitemap expected 48 unique URLs; got {len(urls)}")
    for uri in urls:
        path = local_path(urlsplit(uri).path.replace("https://dlvautomation.ru",""))
        if not path or not (ROOT/path).is_file(): raise AssertionError(f"Missing sitemap page: {uri}")
    ru = data["index.html"][1]
    en = data["en/index.html"][1]
    for file, home in (("index.html",ru),("en/index.html",en)):
        assert home.count('class="service" href=') == 6, f"{file}: expected 6 service cards"
        assert "id=\"contact-form\"" not in home, f"{file}: outdated mailto form"
        assert "id=\"notes-dialog\"" not in home, f"{file}: published internal notes"
        assert "Предварительные показатели для макета" not in home and "Preliminary figures" not in home, file
        assert "id=\"experience\"" not in home, f"{file}: unverified statistics not removed"
    assert "sitemap.xml" in (ROOT/"robots.txt").read_text(encoding="utf-8").lower()
    print(f"PASS: {len(paths)} entry files, {len(urls)} sitemap URLs, {found} local page links")
    print("PASS: no broken local hrefs, shared shells, unique H1/IDs, no public preview notes or draft counters")

if __name__ == "__main__":
    try: main()
    except (AssertionError, ValueError, OSError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        raise SystemExit(1)
