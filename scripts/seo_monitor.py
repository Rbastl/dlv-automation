#!/usr/bin/env python3
"""Read-only SEO checks for DLV Automation. Public data only; no credentials."""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

HOME = "https://dlvautomation.ru"
USER_AGENT = "DLVAutomationSiteMonitor/1.0 (+https://dlvautomation.ru/)"
ROOT = Path("seo-reports")
ROOT.mkdir(exist_ok=True)


def request(url, timeout=14, headers=None, limit=800000):
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xml,application/json,*/*", **(headers or {})}
    req = urllib.request.Request(url, headers=headers)
    # Retry only transient failures of our own website. Third-party probes must
    # respect their limits, and HTTP 404/403 are never retried.
    attempts = 3 if urllib.parse.urlsplit(url).hostname == "dlvautomation.ru" else 1
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise ValueError("Response exceeds configured read limit")
                return response.status, response.geturl(), data
        except urllib.error.HTTPError as exc:
            if exc.code not in (502, 503, 504) or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == attempts - 1:
                raise
        time.sleep(2 * (attempt + 1))


class PageMeta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.h1 = []
        self.description = ""
        self.canonical = ""
        self.robots = ""
        self._in_title = False
        self._h1_depth = 0
        self.h1_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._h1_depth += 1
            self.h1_count += 1
        if tag == "meta":
            if a.get("name", "").lower() == "description":
                self.description = a.get("content", "")
            if a.get("name", "").lower() == "robots":
                self.robots = a.get("content", "")
        if tag == "link":
            if "canonical" in a.get("rel", "").lower().split():
                self.canonical = a.get("href", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._h1_depth = max(self._h1_depth - 1, 0)

    def handle_data(self, data):
        if self._in_title:
            self.title.append(data)
        if self._h1_depth:
            self.h1.append(data)

    def text(self, field):
        return " ".join("".join(getattr(self, field)).split())


def step_summary(markdown):
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as out:
            out.write(markdown + "\n")
    print(markdown[:5000])


def json_save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def audit_site():
    errors, warnings, pages = [], [], []
    try:
        status, _, body = request(HOME + "/robots.txt", timeout=12)
        robots = body.decode("utf-8", errors="replace")
        if status != 200 or not re.search(r"(?im)^Sitemap:\s*https://dlvautomation\.ru/sitemap\.xml\s*$", robots):
            warnings.append("robots.txt exists but sitemap declaration is missing or different.")
    except Exception as exc:
        errors.append("robots.txt: " + str(exc))
    try:
        status, _, body = request(HOME + "/sitemap.xml", timeout=14)
        if status != 200:
            raise ValueError("sitemap HTTP " + str(status))
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        doc = ET.fromstring(body)
        urls = [node.text.strip() for node in doc.findall(".//sm:url/sm:loc", ns) if node.text]
        local_doc = ET.parse("sitemap.xml")
        expected_urls = [node.text.strip() for node in local_doc.findall(".//sm:url/sm:loc", ns) if node.text]
        if not urls or len(urls) != len(set(urls)):
            errors.append("Sitemap is empty or has duplicate URLs.")
        if not expected_urls or len(expected_urls) != len(set(expected_urls)):
            errors.append("Repository sitemap is empty or has duplicate URLs.")
        if urls != expected_urls:
            # On push, Netlify can lag a GitHub commit. Retry a pending deploy,
            # then fail rather than reporting a stale sitemap as a successful audit.
            polls = 12 if os.getenv("GITHUB_EVENT_NAME") == "push" else 0
            for _ in range(polls):
                time.sleep(15)
                status, _, body = request(HOME + "/sitemap.xml", timeout=14)
                if status != 200:
                    continue
                doc = ET.fromstring(body)
                urls = [node.text.strip() for node in doc.findall(".//sm:url/sm:loc", ns) if node.text]
                if urls == expected_urls:
                    break
            if urls != expected_urls:
                missing = sorted(set(expected_urls) - set(urls))
                unexpected = sorted(set(urls) - set(expected_urls))
                errors.append("Published sitemap differs from GitHub main: "
                              f"public={len(urls)}, expected={len(expected_urls)}; "
                              f"missing={len(missing)}, unexpected={len(unexpected)}. "
                              "Production sitemap may be stale: check Timeweb sync or DNS.")
                for link in missing[:8]:
                    warnings.append("Missing on published sitemap: " + link)
    except Exception as exc:
        errors.append("sitemap.xml: " + str(exc))
        urls = []

    for url in urls:
        if not url.startswith(HOME + "/"):
            errors.append("Foreign host in sitemap: " + url[:160])
            continue
        record = {"url": url, "ok": False}
        try:
            status, final_url, body = request(url)
            if status != 200:
                raise ValueError("HTTP " + str(status))
            if urllib.parse.urlsplit(final_url).netloc != "dlvautomation.ru":
                raise ValueError("redirected outside main domain")
            html = body.decode("utf-8", errors="replace")
            p = PageMeta()
            p.feed(html)
            issues = []
            if not p.text("title"):
                issues.append("missing title")
            if p.h1_count != 1:
                issues.append("H1 count " + str(p.h1_count))
            if "noindex" in p.robots.lower():
                issues.append("noindex")
            if p.canonical.rstrip("/") != url.rstrip("/"):
                issues.append("canonical mismatch: " + p.canonical[:130])
            if not p.description.strip():
                warnings.append("Missing meta description: " + url)
            record.update(ok=not issues, http=status, title=p.text("title")[:140], issues=issues)
            if issues:
                errors.append(url + ": " + ", ".join(issues))
        except Exception as exc:
            record["issues"] = [str(exc)]
            errors.append(url + ": " + str(exc))
        pages.append(record)
        time.sleep(0.12)

    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": HOME,
        "sitemap_pages": len(urls),
        "checked": len(pages),
        "ok": sum(bool(row.get("ok")) for row in pages),
        "errors": errors,
        "warnings": warnings,
        "pages": pages,
    }
    json_save(ROOT / "site.json", report)
    text = ("## DLV Automation · проверка сайта\n\n"
            f"Страниц: **{len(pages)}**, проверены без ошибок: **{report['ok']}**. "
            f"Ошибок: **{len(errors)}**; предупреждений: **{len(warnings)}**.\n\n"
            + ("\n".join("- ❌ " + msg[:220] for msg in errors[:15]) if errors else "✅ Критичных ошибок не обнаружено.")
            + ("\n\n" + "\n".join("- ⚠️ " + msg[:220] for msg in warnings[:10]) if warnings else ""))
    step_summary(text)
    return 1 if errors else 0


def previous_public_snapshot():
    """Try last workflow artifact; missing history must not block monitoring."""
    token = os.getenv("GH_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    if not token or not repository:
        return {}
    try:
        url = f"https://api.github.com/repos/{repository}/actions/artifacts?name=dlv-public-competitors&per_page=30"
        _, _, body = request(url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        artifacts = json.loads(body).get("artifacts", [])
        run_id = str(os.getenv("GITHUB_RUN_ID", ""))
        candidates = [a for a in artifacts if not a.get("expired")
                      and str(a.get("workflow_run", {}).get("id", "")) != run_id]
        if not candidates:
            return {}
        latest = max(candidates, key=lambda x: x.get("created_at", ""))
        _, _, zipped = request(latest["archive_download_url"], timeout=20, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
        }, limit=2000000)
        with zipfile.ZipFile(io.BytesIO(zipped)) as archive:
            name = next((n for n in archive.namelist() if n.endswith("competitors.json")), None)
            if name:
                old = json.loads(archive.read(name))
                return {x["url"]: x for x in old.get("pages", [])}
    except Exception as exc:
        print("Previous public baseline unavailable:", type(exc).__name__)
    return {}


def robots_allowed(url):
    parsed = urllib.parse.urlsplit(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        status, _, body = request(robots_url, timeout=10, limit=150000)
        if status != 200:
            return False, "No readable robots.txt; skip conservatively"
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(body.decode("utf-8", errors="replace").splitlines())
        return parser.can_fetch(USER_AGENT, url), "robots.txt checked"
    except Exception:
        return False, "robots.txt inaccessible; skip conservatively"


def audit_competitors():
    cfg = json.loads(Path("seo/competitors.json").read_text(encoding="utf-8"))
    old = previous_public_snapshot()
    records, changed, skipped = [], [], []
    for item in cfg["sites"]:
        url = item["url"]
        allowed, note = robots_allowed(url)
        row = {"name": item["name"], "url": url, "status": "skipped", "note": note}
        if allowed:
            try:
                status, final, body = request(url, timeout=14, limit=600000)
                if status != 200:
                    raise ValueError("HTTP " + str(status))
                p = PageMeta()
                p.feed(body.decode("utf-8", errors="replace"))
                row.update(status="ok", title=p.text("title")[:180],
                           h1=p.text("h1")[:180], description=p.description[:220],
                           final_url=final, note="")
                prev = old.get(url)
                if prev and prev.get("status") == "ok":
                    for field in ("title", "h1", "description"):
                        if row.get(field) != prev.get(field):
                            changed.append(f"{item['name']}: изменился {field}")
                elif prev is None:
                    row["note"] = "No previous baseline (first observation)"
            except Exception as exc:
                row.update(status="unavailable", note=type(exc).__name__ + ": " + str(exc)[:130])
        if row["status"] != "ok":
            skipped.append(item["name"] + " — " + row["note"][:90])
        records.append(row)
        time.sleep(1)
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "pages": records}
    json_save(ROOT / "competitors.json", report)
    msg = ("## DLV Automation · еженедельный срез конкурентов\n\n"
           f"Обработано **{sum(p['status']=='ok' for p in records)}** из **{len(records)}** сайтов.\n\n"
           + ("\n".join("- " + x for x in changed) if changed else "Изменений по сравнению с предыдущим доступным срезом не обнаружено или предыдущего среза нет.")
           + ("\n\nНедоступные/пропущенные:\n" + "\n".join("- " + s for s in skipped) if skipped else ""))
    step_summary(msg)
    return 0  # third-party blocks are not failures of the DLV website


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", action="store_true")
    parser.add_argument("--competitors", action="store_true")
    args = parser.parse_args()
    if not args.site and not args.competitors:
        parser.error("Choose --site or --competitors")
    return audit_site() if args.site else audit_competitors()


if __name__ == "__main__":
    sys.exit(main())
