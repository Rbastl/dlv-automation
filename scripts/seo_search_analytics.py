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

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

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
    if already_collected(session, "Google", period):
        summary("Google Search Console: период уже загружен, дубли не создавались.")
        return
    endpoint = ("https://www.googleapis.com/webmasters/v3/sites/"
                + urllib.parse.quote(property_url, safe="") + "/searchAnalytics/query")
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
    user = valid_response(requests.get(WEBMASTER + "/user",
                                       headers=headers, timeout=25), "Yandex user")
    user_id = user.get("user_id")
    if user_id is None:
        raise RuntimeError("Yandex user: no user_id")
    base = f"{WEBMASTER}/user/{urllib.parse.quote(str(user_id), safe='')}"
    hosts_data = valid_response(requests.get(base + "/hosts",
                                             headers=headers, timeout=25), "Yandex hosts")
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
    result = valid_response(requests.get(url, headers=headers, params=params,
                                         timeout=35), "Yandex search queries")
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
    for name, run in (("Google", google_collect), ("Яндекс", yandex_collect)):
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
