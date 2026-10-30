#!/usr/bin/env python3
"""DLV: Yandex Webmaster -> private Google Sheets. No secrets or queries in public logs.

This collector is independent from the Google Search Console job.
The Yandex site must belong to the OAuth user's verified HTTPS property.
Sitemap is registered once, never duplicated; re-crawl is manual opt-in only.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

SITE = "https://dlvautomation.ru/"
SITEMAP = SITE + "sitemap.xml"
BASE = "https://api.webmaster.yandex.net/v4"
SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets/"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PRIORITY_PATHS = [
    "scada-hmi/", "siemens-tia-portal/", "modernizaciya-asu-tp/",
    "outsourcing-asu-tp/",
]
OPTIONAL_CODES = {"HOST_NOT_INDEXED", "HOST_NOT_LOADED"}


def report(message):
    print(message)
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as out:
            out.write(message + "\n")


def sitemap_urls():
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    doc = ET.parse(Path("sitemap.xml"))
    urls = [x.text.strip() for x in doc.findall(".//s:url/s:loc", ns) if x.text]
    if not urls or len(urls) != len(set(urls)):
        raise RuntimeError("Local sitemap missing or duplicated URLs")
    if any(not u.startswith(SITE) for u in urls):
        raise RuntimeError("Foreign URL in sitemap")
    return urls


def request_yandex(method, path, headers, label, params=None, payload=None,
                   optional=False, conflict_ok=False):
    import requests

    url = BASE + path
    for attempt in range(3):
        try:
            resp = requests.request(
                method, url, headers=headers, params=params, json=payload,
                timeout=(10, 30),
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == 2 or method.upper() != "GET":
                raise RuntimeError("Yandex " + label + ": network unavailable") from None
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code in (500, 502, 503, 504) and attempt < 2 and method.upper() == "GET":
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code == 409 and conflict_ok:
            return {"already_exists": True}
        if resp.status_code >= 400:
            try:
                code = str(resp.json().get("error_code", ""))[:64]
            except (ValueError, TypeError, AttributeError):
                code = ""
            if optional and resp.status_code == 404 and code in OPTIONAL_CODES:
                return None
            # Never print response content, OAuth token, request URL, or private queries.
            raise RuntimeError("Yandex " + label + ": HTTP " + str(resp.status_code)
                               + (" (" + code + ")" if code else ""))
        try:
            return resp.json()
        except ValueError:
            raise RuntimeError("Yandex " + label + ": invalid JSON") from None
    raise RuntimeError("Yandex " + label + ": retry limit")


def get_verified_host(headers):
    info = request_yandex("GET", "/user", headers, "user")
    uid = info.get("user_id")
    if uid is None:
        raise RuntimeError("Yandex API user_id missing")
    user_path = "/user/" + urllib.parse.quote(str(uid), safe="")
    sites = request_yandex("GET", user_path + "/hosts", headers, "hosts")
    matches = [
        host for host in sites.get("hosts", [])
        if host.get("ascii_host_url", "").rstrip("/") + "/" == SITE
    ]
    if not matches:
        raise RuntimeError("DLV HTTPS property not present in authorized Yandex account")
    host = next((h for h in matches if h.get("verified") is True), None)
    if not host:
        raise RuntimeError("DLV HTTPS property exists but Yandex rights are not verified")
    host_id = host.get("host_id")
    if not host_id:
        raise RuntimeError("Yandex host_id missing")
    base = user_path + "/hosts/" + urllib.parse.quote(str(host_id), safe="")
    mirror = (host.get("main_mirror") or {}).get("ascii_host_url", SITE)
    return base, mirror.rstrip("/") + "/" == SITE


def ensure_sitemap(base, headers):
    data = request_yandex("GET", base + "/user-added-sitemaps",
                          headers, "sitemap list", params={"limit": 100})
    registered = any(row.get("sitemap_url") == SITEMAP
                     for row in data.get("sitemaps", []))
    if registered:
        return "уже добавлен"
    result = request_yandex("POST", base + "/user-added-sitemaps",
                            headers, "sitemap registration",
                            payload={"url": SITEMAP}, conflict_ok=True)
    return "уже добавлен" if result.get("already_exists") else "добавлен"


def metric_series(data, name, start, end):
    items = (data or {}).get("indicators", {}).get(name, [])
    return {str(row.get("date", ""))[:10]: float(row["value"])
            for row in items
            if str(row.get("date", ""))[:10] >= start
            and str(row.get("date", ""))[:10] <= end
            and isinstance(row.get("value"), (int, float))}


def site_totals(base, headers, start, end):
    indicators = ["TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION"]
    params = [("query_indicator", value) for value in indicators]
    params += [("date_from", start), ("date_to", end)]
    data = request_yandex("GET", base + "/search-queries/all/history",
                          headers, "total search history", params=params, optional=True)
    if data is None:
        return None
    shows = metric_series(data, "TOTAL_SHOWS", start, end)
    clicks = metric_series(data, "TOTAL_CLICKS", start, end)
    positions = metric_series(data, "AVG_SHOW_POSITION", start, end)
    if not shows and not clicks:
        return None
    shown = round(sum(shows.values()), 3) if shows else ""
    clicked = round(sum(clicks.values()), 3) if clicks else ""
    weight = sum(shows.get(day, 0) for day in positions)
    avg = round(sum(positions[d] * shows.get(d, 0) for d in positions) / weight, 2) if weight else ""
    days = len(set(shows) | set(clicks))
    return [start, end, shown, clicked, avg, days]


def popular_queries(base, headers, start, end):
    params = [("order_by", "TOTAL_SHOWS"), ("limit", "500"),
              ("date_from", start), ("date_to", end)]
    for metric in ("TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION",
                   "AVG_CLICK_POSITION"):
        params.append(("query_indicator", metric))
    data = request_yandex("GET", base + "/search-queries/popular",
                          headers, "popular queries", params=params, optional=True)
    if data is None:
        return []
    result = []
    for item in data.get("queries", []):
        query = item.get("query_text", "")
        if not isinstance(query, str) or not query:
            continue
        metrics = item.get("indicators") or {}
        result.append([start, end, query,
                       metrics.get("TOTAL_SHOWS", ""), metrics.get("TOTAL_CLICKS", ""),
                       metrics.get("AVG_SHOW_POSITION", ""),
                       metrics.get("AVG_CLICK_POSITION", "")])
    return result


def indexed_pages(base, headers, start, end):
    data = request_yandex("GET", base + "/search-urls/in-search/history",
                          headers, "pages in search", params={
                              "date_from": start, "date_to": end,
                          }, optional=True)
    if data is None:
        return ""
    records = [row for row in data.get("history", [])
               if isinstance(row.get("value"), (int, float))]
    if not records:
        return ""
    last = max(records, key=lambda x: x.get("date", ""))
    return int(last["value"])


def append_sheet(session, sheet_id, tab, values):
    if not values:
        return
    quoted = urllib.parse.quote("'" + tab + "'!A:K", safe="")
    url = SHEETS_BASE + sheet_id + "/values/" + quoted + ":append"
    response = session.post(url, params={
        "valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS",
    }, json={"majorDimension": "ROWS", "values": values}, timeout=45)
    if response.status_code >= 400:
        raise RuntimeError("Private Google Sheet write failed (HTTP "
                           + str(response.status_code) + ")")


def already_collected(session, sheet_id, tab, start, end):
    quoted = urllib.parse.quote("'" + tab + "'!A2:B", safe="")
    response = session.get(SHEETS_BASE + sheet_id + "/values/" + quoted, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError("Private Google Sheet access failed (HTTP "
                           + str(response.status_code) + ")")
    return any(len(row) >= 2 and row[0] == start and row[1] == end
               for row in response.json().get("values", []))


def recrawl_queue(base, headers):
    """Read queue before any re-crawl write: POST responses can time out after acceptance."""
    data = request_yandex("GET", base + "/recrawl/queue", headers,
                          "recrawl queue", params={"limit": 100})
    return {task.get("url"): task.get("state", "")
            for task in data.get("tasks", []) if task.get("url")}


def maybe_reindex(base, headers, site_urls):
    if os.getenv("DLV_YANDEX_RECRAWL", "false").lower() != "true":
        return
    wanted = [SITE + path for path in PRIORITY_PATHS]
    if any(url not in site_urls for url in wanted):
        raise RuntimeError("Priority page missing from local sitemap")
    existing = recrawl_queue(base, headers)
    quota = request_yandex("GET", base + "/recrawl/quota", headers,
                           "recrawl quota")
    remaining = int(quota.get("quota_remainder", 0))
    accepted = 0
    previously = 0
    skipped_quota = 0
    for url in wanted:
        if url in existing:
            previously += 1
            continue
        if remaining <= 0:
            skipped_quota += 1
            continue
        try:
            reply = request_yandex("POST", base + "/recrawl/queue", headers,
                                   "priority recrawl", payload={"url": url},
                                   conflict_ok=True)
        except RuntimeError:
            # A failed POST is not necessarily rejected. Inspect the queue
            # before considering another attempt; never blindly replay a POST.
            updated = recrawl_queue(base, headers)
            if url in updated:
                previously += 1
                existing = updated
                remaining = max(0, remaining - 1)
                continue
            raise RuntimeError("Yandex recrawl request not confirmed; "
                               "queue checked, no automatic POST retry") from None
        if reply.get("already_exists"):
            previously += 1
        else:
            accepted += 1
            remaining -= 1
        existing[url] = "IN_PROGRESS"
    report("Яндекс: переобход коммерческих страниц — новых запросов **"
           + str(accepted) + "**; уже в очереди **" + str(previously)
           + "**; не отправлено из-за квоты **" + str(skipped_quota)
           + "**. Добавление в очередь не гарантирует индексацию.")


def main():
    token = os.getenv("YANDEX_WEBMASTER_TOKEN", "").strip()
    sheet_id = os.getenv("DLV_SEO_SHEET_ID", "").strip()
    service_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not token:
        report("⚠️ Яндекс: OAuth не доступен в GitHub Actions (YANDEX_WEBMASTER_TOKEN). "
               "Google работает независимо; добавьте токен только в GitHub Secrets.")
        return 1
    if not sheet_id or not service_json:
        report("⚠️ Яндекс: нет доступа к закрытой Google-таблице; проверьте GitHub Secrets.")
        return 1
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    try:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(service_json), scopes=GOOGLE_SCOPES)
        google = AuthorizedSession(creds)
        headers = {"Authorization": "OAuth " + token, "Accept": "application/json"}
        urls = sitemap_urls()
        host, primary = get_verified_host(headers)
        if not primary:
            report("⚠️ Яндекс: подтверждённый сайт не указан главным зеркалом. "
                   "Проверьте главное зеркало в Вебмастере.")
        sitemap_status = ensure_sitemap(host, headers)
        now = datetime.now(timezone.utc)
        period_end = (now - timedelta(days=3)).date()
        period_start = period_end - timedelta(days=6)
        start, end = period_start.isoformat(), period_end.isoformat()
        stamp = now.isoformat(timespec="seconds")
        if not already_collected(google, sheet_id, "Яндекс — сводка", start, end):
            summary = site_totals(host, headers, start, end)
            if summary is not None:
                append_sheet(google, sheet_id, "Яндекс — сводка",
                             [summary + [stamp]])
        if not already_collected(google, sheet_id, "Яндекс", start, end):
            queries = popular_queries(host, headers, start, end)
            append_sheet(google, sheet_id, "Яндекс",
                         [row + [stamp] for row in queries])
        pages = indexed_pages(host, headers,
                              (now - timedelta(days=21)).date().isoformat(),
                              now.date().isoformat())
        condition = "OK" if pages != "" else "Данные об индексе ещё не поступили"
        if not primary:
            condition += "; главное зеркало отличается"
        append_sheet(google, sheet_id, "Яндекс — индексация", [[
            stamp, SITE, "Да", pages, sitemap_status, len(urls), condition,
        ]])
        maybe_reindex(host, headers, urls)
        report("✅ Яндекс Вебмастер: права на HTTPS-сайт подтверждены, "
               "Sitemap " + sitemap_status + ", URL: **" + str(len(urls)) + "**.")
        report("Поисковые запросы, сводка и история индекса сохранены в закрытую "
               "Google-таблицу, если Яндекс уже предоставил данные. "
               "Google собирается независимо.")
        return 0
    except Exception as exc:
        # Only carefully constructed messages; never expose credentials, URLs with tokens,
        # upstream bodies, private search queries, or full tracebacks in public logs.
        report("⚠️ Яндекс Вебмастер: настройка не завершена — " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
