#!/usr/bin/env python3
"""Private DLV SEO analytics: GSC and Yandex -> private Google Sheet.

Credentials come ONLY from GitHub Actions secrets. Search queries and numbers
are never printed to workflow logs or written to this public repository.
"""
import json
import os
import sys
import urllib.parse
from datetime import date, datetime, timedelta, timezone

import time

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]
SHEET_ID = os.getenv("DLV_SEO_SHEET_ID", "").strip()
SA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
YANDEX_TOKEN = os.getenv("YANDEX_WEBMASTER_TOKEN", "").strip()
SITE_HOST = "dlvautomation.ru"
SHEETS = "https://sheets.googleapis.com/v4/spreadsheets/"
WEBMASTER = "https://api.webmaster.yandex.net/v4"
PAGE_REPORT_LIMIT = 1000
PAGE_REPAIR_WINDOWS = 3


def summary(text):
    """No site analytics or tokens in publicly readable Actions logs."""
    print(text)
    if (path := os.getenv("GITHUB_STEP_SUMMARY")):
        with open(path, "a", encoding="utf-8") as out:
            out.write(text + "\n")


def valid_response(response, context):
    if response.status_code >= 400:
        raise RuntimeError(f"{context}: HTTP {response.status_code}")
    return response.json()


def tab_range(tab, a1):
    return urllib.parse.quote(f"'{tab}'!{a1}", safe="")


def already_collected(session, tab, period):
    link = f"{SHEETS}{SHEET_ID}/values/{tab_range(tab, 'A2:B')}"
    data = valid_response(session.get(link, timeout=25), f"{tab} read")
    return any(len(r) >= 2 and r[0] == period[0] and r[1] == period[1]
               for r in data.get("values", []))


def append_private(session, tab, rows):
    if not rows:
        return False
    url = f"{SHEETS}{SHEET_ID}/values/{tab_range(tab, 'A:I')}:append"
    reply = session.post(url, params={
        "valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"
    }, json={"majorDimension": "ROWS", "values": rows}, timeout=40)
    valid_response(reply, f"{tab} append")
    return True



def owned_page_url(url):
    """Keep the exact GSC URI, including HTTP/www, for our own hosts only."""
    if not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
        return (parsed.scheme in ("http", "https")
                and parsed.hostname in (SITE_HOST, "www." + SITE_HOST)
                and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


def stored_page_keys(session):
    """Read existing period/URI identities without logging private rows."""
    url = f"{SHEETS}{SHEET_ID}/values/{tab_range('Страницы', 'A2:C')}"
    data = valid_response(session.get(url, timeout=25), "Page report identities")
    return {tuple(row[:3]) for row in data.get("values", [])
            if len(row) >= 3 and owned_page_url(row[2])}


def page_periods_to_repair(period, existing):
    """Bound recovery to three recent stored weeks plus the current week."""
    first, last = map(date.fromisoformat, period)
    if last - first != timedelta(days=6):
        raise ValueError("Page report requires a complete seven-day window")
    recent = set()
    for start, end, _ in existing:
        try:
            left, right = date.fromisoformat(start), date.fromisoformat(end)
        except (TypeError, ValueError):
            continue
        if (right - left == timedelta(days=6)
                and first - timedelta(days=30) <= left
                and right <= last and (start, end) != tuple(period)):
            recent.add((start, end))
    return [tuple(period)] + sorted(recent, reverse=True)[:PAGE_REPAIR_WINDOWS]


def reconcile_google_pages(session, endpoint, period, stamp, existing):
    """Append missing URIs only; never rewrite or merge historical URI rows."""
    rows, seen, offset = [], set(), 0
    while True:
        response = valid_response(session.post(endpoint, json={
            "startDate": period[0], "endDate": period[1],
            "dimensions": ["page"], "type": "web",
            "rowLimit": PAGE_REPORT_LIMIT, "startRow": offset,
        }, timeout=35), "Search Console pages report")
        batch = response.get("rows", [])
        for line in batch:
            keys = line.get("keys", [])
            if not keys or not owned_page_url(keys[0]):
                continue
            url = keys[0]
            identity = (period[0], period[1], url)
            if identity in existing or url in seen:
                continue
            seen.add(url)
            rows.append([
                period[0], period[1], url,
                line.get("clicks", 0), line.get("impressions", 0),
                line.get("ctr", 0), line.get("position", 0), stamp
            ])
        if len(batch) < PAGE_REPORT_LIMIT:
            break
        offset += len(batch)
    # Complete all API pages before writing: a later-page error must not leave
    # a partially imported period that the next run would skip.
    if append_private(session, "Страницы", rows):
        existing.update((row[0], row[1], row[2]) for row in rows)
        summary("Google Search Console: недостающие URL записаны в закрытую вкладку «Страницы».")
    else:
        summary("Google Search Console: новых строк по URL нет; существующие данные сохранены.")


def google_summary_and_pages(session, endpoint, period, stamp):
    """Store total impressions (including anonymous queries) and page-level KPIs.

    Query anonymization and property/page aggregation are different effects.
    Preserve all owned URI variants; do not force page sums to site totals.
    All data remains in the private spreadsheet.
    """
    if not already_collected(session, "Сводка", period):
        response = valid_response(session.post(endpoint, json={
            "startDate": period[0], "endDate": period[1],
            "type": "web", "rowLimit": 1,
        }, timeout=35), "Search Console site totals")
        metric = (response.get("rows") or [{}])[0]
        append_private(session, "Сводка", [[
            period[0], period[1],
            metric.get("clicks", 0), metric.get("impressions", 0),
            metric.get("ctr", 0), metric.get("position", 0), stamp
        ]])
        summary("Google Search Console: суммарные показатели записаны в закрытую вкладку «Сводка».")
    existing = stored_page_keys(session)
    for window in page_periods_to_repair(period, existing):
        reconcile_google_pages(session, endpoint, window, stamp, existing)


def google_collect(session, start, end, stamp):
    sites_data = valid_response(
        session.get("https://www.googleapis.com/webmasters/v3/sites", timeout=25),
        "Search Console site list"
    )
    accessible = [x.get("siteUrl", "") for x in sites_data.get("siteEntry", [])]
    desired = ["sc-domain:" + SITE_HOST, "https://" + SITE_HOST + "/",
               "https://www." + SITE_HOST + "/"]
    property_url = next((s for s in desired if s in accessible), None)
    if not property_url:
        summary("Google Search Console: технической учётной записи не предоставлен доступ к ресурсу DLV.")
        return
    period = [str(start), str(end)]
    endpoint = ("https://www.googleapis.com/webmasters/v3/sites/"
                + urllib.parse.quote(property_url, safe="") + "/searchAnalytics/query")
    google_summary_and_pages(session, endpoint, period, stamp)
    if already_collected(session, "Google", period):
        summary("Google Search Console: поисковые запросы за период уже загружены, дубли не создавались.")
        return
    response = session.post(endpoint, json={
        "startDate": period[0], "endDate": period[1],
        "dimensions": ["query", "page"], "type": "web", "rowLimit": 1000,
    }, timeout=35)
    result = valid_response(response, "Search Console search analytics")
    rows = []
    for line in result.get("rows", []):
        keys = line.get("keys", [])
        if len(keys) < 2:
            continue
        rows.append([period[0], period[1], keys[0], keys[1],
                     line.get("clicks", 0), line.get("impressions", 0),
                     line.get("ctr", 0), line.get("position", 0), stamp])
    if append_private(session, "Google", rows):
        summary("Google Search Console: поисковые данные записаны в закрытую Google-таблицу.")
    else:
        summary("Google Search Console: за период пока нет доступных поисковых строк.")




def yandex_get(url, context, **kwargs):
    """Retry transient API transport failures; log only safe diagnostic categories."""
    import requests
    for attempt in range(3):
        try:
            return valid_response(requests.get(url, **kwargs), context)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if attempt < 2:
                time.sleep((2, 5)[attempt])
                continue
            kind = type(exc).__name__
            reason = str(exc).lower()
            if "nameresolutionerror" in reason or "failed to resolve" in reason or "getaddrinfo" in reason:
                kind += "/DNS"
            elif "proxyerror" in reason or "proxy" in reason:
                kind += "/proxy"
            elif "ssl" in reason or "certificate" in reason:
                kind += "/TLS"
            elif "connection refused" in reason or "connection reset" in reason:
                kind += "/connection"
            summary("Яндекс Вебмастер: сетевой сбой на этапе " + context
                    + " (" + kind + ", 3 попытки).")
            raise RuntimeError("Yandex connectivity failed at " + context) from None


def yandex_collect(session, start, end, stamp):
    if not YANDEX_TOKEN:
        summary("Яндекс Вебмастер: OAuth-токен ещё не задан в GitHub Secrets.")
        return
    period = [str(start), str(end)]
    if already_collected(session, "Яндекс", period):
        summary("Яндекс Вебмастер: период уже загружен, дубли не создавались.")
        return
    headers = {"Authorization": "OAuth " + YANDEX_TOKEN,
               "Accept": "application/json"}
    user = yandex_get(WEBMASTER + "/user", "Yandex user",
                      headers=headers, timeout=25)
    user_id = user.get("user_id")
    if user_id is None:
        raise RuntimeError("Yandex user: no user_id")
    base = f"{WEBMASTER}/user/{urllib.parse.quote(str(user_id), safe='')}"
    hosts_data = yandex_get(base + "/hosts", "Yandex hosts",
                            headers=headers, timeout=25)
    hosts = hosts_data.get("hosts", [])
    candidates = [h for h in hosts if h.get("verified")
                  and urllib.parse.urlsplit(h.get("ascii_host_url", "")).hostname in
                  (SITE_HOST, "www." + SITE_HOST)]
    if not candidates:
        summary("Яндекс Вебмастер: среди сайтов этого OAuth-пользователя нет подтверждённого DLV.")
        return
    candidates.sort(key=lambda h: h.get("ascii_host_url", "") != "https://" + SITE_HOST + "/")
    host_id = candidates[0].get("host_id")
    if not host_id:
        raise RuntimeError("Yandex hosts: empty host_id")
    url = (base + "/hosts/" + urllib.parse.quote(str(host_id), safe="")
           + "/search-queries/popular")
    params = [
        ("order_by", "TOTAL_SHOWS"),
        ("query_indicator", "TOTAL_SHOWS"),
        ("query_indicator", "TOTAL_CLICKS"),
        ("query_indicator", "AVG_SHOW_POSITION"),
        ("query_indicator", "AVG_CLICK_POSITION"),
        ("date_from", period[0]), ("date_to", period[1]),
        ("limit", "250"),
    ]
    result = yandex_get(url, "Yandex search queries",
                        headers=headers, params=params, timeout=35)
    rows = []
    for entry in result.get("queries", []):
        i = entry.get("indicators", {})
        rows.append([period[0], period[1], entry.get("query_text", ""),
                     i.get("TOTAL_SHOWS", ""), i.get("TOTAL_CLICKS", ""),
                     i.get("AVG_SHOW_POSITION", ""), i.get("AVG_CLICK_POSITION", ""),
                     stamp])
    if append_private(session, "Яндекс", rows):
        summary("Яндекс Вебмастер: поисковые данные записаны в закрытую Google-таблицу.")
    else:
        summary("Яндекс Вебмастер: за период пока нет доступных поисковых строк.")


def main():
    if not SHEET_ID or not SA_JSON:
        summary("⚠️ Автовыгрузка пока не активна: в GitHub Secrets отсутствуют Google credential или ID таблицы. Регистрация самого сайта не требуется.")
        return 0
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession

        info = json.loads(SA_JSON)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=GOOGLE_SCOPES)
        session = AuthorizedSession(creds)
    except Exception as exc:
        summary("Ошибка при создании Google API-сессии: " + type(exc).__name__)
        return 1
    today = datetime.now(timezone.utc).date()
    end = today - timedelta(days=3)
    start = end - timedelta(days=6)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    failed = False
    collectors = [("Google", google_collect)]
    if os.getenv("DLV_YANDEX_ENABLED", "false").strip().lower() in ("1", "true", "yes"):
        collectors.append(("Яндекс", yandex_collect))
    else:
        summary("Яндекс Вебмастер: временно приостановлен; Google работает независимо.")
    for name, run in collectors:
        try:
            run(session, start, end, stamp)
        except Exception as exc:
            failed = True
            # Do not disclose OAuth tokens, request bodies, query strings or private data.
            summary(name + ": ошибка загрузки (" + type(exc).__name__
                    + "). Проверьте права API и вкладку Actions.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

