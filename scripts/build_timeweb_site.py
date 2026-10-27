#!/usr/bin/env python3
"""Build the public DLV Automation site for Timeweb.

Never upload the full repository root: GitHub workflows, automation source,
SEO research and repository metadata do not belong under public_html.
"""
from pathlib import Path
from shutil import copy2, rmtree
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

SOURCE = Path(".")
DEST = Path("site-dist")
STATIC_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".svg", ".png", ".jpg", ".jpeg",
    ".webp", ".gif", ".ico", ".txt", ".xml", ".webmanifest",
    ".woff", ".woff2", ".ttf", ".otf", ".avif", ".mp4", ".pdf",
}
EXCLUDED_DIRS = {
    ".git", ".github", "scripts", "seo", "site-dist", "__pycache__",
    "node_modules", ".venv", "vendor", "tests", "test",
}
PUBLIC_ROOT_FILES = {
    "index.html", "404.html", "robots.txt", "sitemap.xml", "feed.xml", "favicon.svg",
    "yandex_abd6fd29640c5931.html",
}

def allowed(path):
    parts = path.parts
    if not path.is_file() or any(p.startswith(".") or p in EXCLUDED_DIRS for p in parts):
        return False
    if len(parts) == 1:
        return path.name in PUBLIC_ROOT_FILES
    return path.suffix.lower() in STATIC_EXTENSIONS


def main():
    if DEST.exists():
        rmtree(DEST)
    count = 0
    for path in sorted(SOURCE.rglob("*")):
        if not allowed(path):
            continue
        target = DEST / path
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(path, target)
        count += 1

    # Timeweb virtual hosting accepts Apache-style .htaccess.
    # Prefer our current index.html to the default placeholder index.htm.
    (DEST / ".htaccess").write_text(
        "DirectoryIndex index.html index.htm\n"
        "ErrorDocument 404 /404.html\n"
        "Redirect 301 /razrabotka-scada/ /scada-hmi/\n"
        "Redirect 301 /en/scada-hmi-development/ /en/scada-hmi/\n",
        encoding="utf-8",
    )

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    tree = ET.parse(DEST / "sitemap.xml")
    urls = [el.text.strip() for el in tree.findall(".//sm:url/sm:loc", ns) if el.text]
    if not urls or len(urls) != len(set(urls)):
        sys.exit("ERROR: Missing or duplicate sitemap URLs.")
    missing = []
    for url in urls:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "dlvautomation.ru":
            sys.exit("ERROR: Foreign or non-HTTPS URL in sitemap.")
        path = parsed.path.lstrip("/")
        page = DEST / path / "index.html" if path.endswith("/") or not path else DEST / path
        if not page.is_file():
            missing.append(path)
    if missing:
        sys.exit("ERROR: Missing pages: " + ", ".join(missing[:20]))
    if not (DEST / "feed.xml").is_file():
        sys.exit("ERROR: RSS feed missing from public website package.")
    if not (DEST / "index.html").exists() or not (DEST / "robots.txt").exists():
        sys.exit("ERROR: Required entry files missing.")
    print(f"Timeweb publishing package prepared: {count} public files, {len(urls)} sitemap URLs.")
    print("Excluded from published package: GitHub metadata, scripts, SEO research and credentials.")

if __name__ == "__main__":
    main()
