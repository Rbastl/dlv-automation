#!/usr/bin/env python3
"""DLV Google-only index audit. Search Console inspection data stays in private Sheets.

No credentials, inspection records or customer data are committed to GitHub.
The API inspects Google's *indexed* URL version; it does not request indexing.
"""
import json
import os
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

HOST = "dlvautomation.ru"
SHEET_ID = os.getenv("DLV_SEO_SHEET_ID", "").strip()
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
INSPECTION_ENDPOINT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
SHEETS = "https://sheets.googleapis.com/v4/spreadsheets/"
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]


def summary(message):
    print(message)
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as out:
            out.write(message + "\n")


def data_or_error(response, task):
    if response.status_code >= 400:
        raise RuntimeError(task + " HTTP " + str(response.status_code))
    return response.json()


def property_url(session):
    entries = data_or_error(
        session.get("https://www.googleapis.com/webmasters/v3/sites", timeout=25),
        "Search Console property list"
    ).get("siteEntry", [])
    active = {x.get("siteUrl", "") for x in entries}
    options = ["sc-domain:" + HOST, "https://" + HOST + "/",
               "https://www." + HOST + "/"]
    return next((candidate for candidate in options if candidate in active), None)


def site_urls():
    doc = ET.parse(Path("sitemap.xml"))
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [e.text.strip() for e in doc.findall(".//s:url/s:loc", ns) if e.text]
    if not urls or len(urls) != len(set(urls)):
        raise ValueError("Repository sitemap empty or contains duplicates")
    if any(not url.startswith("https://" + HOST + "/") for url in urls):
        raise ValueError("Repository sitemap contains external URLs")
    return urls


def append_private(session, records):
    endpoint = (SHEETS + SHEET_ID + "/values/"
                + urllib.parse.quote("'Индексация'!A:K", safe="") + ":append")
    result = session.post(endpoint, params={
        "valueInputOption": "RAW",
        "insertDataOption": "INSERT_ROWS",
    }, json={"majorDimension": "ROWS", "values": records}, timeout=45)
    data_or_error(result, "Private index sheet append")


def inspect(session, url, prop):
    response = session.post(INSPECTION_ENDPOINT, json={
        "inspectionUrl": url, "siteUrl": prop, "languageCode": "ru-RU",
    }, timeout=25)
    result = data_or_error(response, "Google URL inspection")
    detail = result.get("inspectionResult", {})
    state = detail.get("indexStatusResult", {})
    return [
        state.get("verdict", "VERDICT_UNSPECIFIED"),
        state.get("coverageState", ""),
        state.get("pageFetchState", ""),
        state.get("robotsTxtState", ""),
        state.get("indexingState", ""),
        state.get("lastCrawlTime", ""),
        state.get("googleCanonical", ""),
        state.get("userCanonical", ""),
        detail.get("inspectionResultLink", ""),
    ]


def main():
    if not SHEET_ID or not SERVICE_ACCOUNT_JSON:
        summary("⚠️ Google indexing: сервисные данные не настроены в GitHub Secrets. Проверка не выполнена.")
        return 1
    try:
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(SERVICE_ACCOUNT_JSON), scopes=SCOPES)
        session = AuthorizedSession(credentials)
        site = property_url(session)
        if not site:
            summary("⚠️ Google indexing: сервисной учётной записи не доступен ресурс dlvautomation.ru.")
            return 1
        urls = site_urls()
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = []
        verdicts = Counter()
        issues = 0
        for url in urls:
            try:
                fields = inspect(session, url, site)
                verdicts[fields[0]] += 1
            except Exception as exc:
                issues += 1
                fields = ["API_ERROR", type(exc).__name__, "", "", "", "", "", "", ""]
            rows.append([stamp, url] + fields)
            time.sleep(0.23)
        append_private(session, rows)
        summary(
            "## DLV · индексация в Google\n\n"
            + "Проверено URL: **" + str(len(rows)) + "**. "
            + "Проиндексировано (PASS): **" + str(verdicts.get("PASS", 0)) + "**. "
            + "Исключено (NEUTRAL): **" + str(verdicts.get("NEUTRAL", 0)) + "**. "
            + "Ошибки индекса (FAIL): **" + str(verdicts.get("FAIL", 0)) + "**. "
            + "Сбои API: **" + str(issues) + "**.\n\n"
            + "Подробные статусы каждого URL записаны в закрытую вкладку «Индексация». "
            + "Не является запросом ускоренной индексации."
        )
        return 1 if issues else 0
    except Exception as exc:
        summary("⚠️ Google indexing audit failed: " + type(exc).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
