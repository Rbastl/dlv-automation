#!/usr/bin/env python3
"""Offline regression tests: never contact Yandex or private Google Sheets."""
import os
import unittest
from unittest.mock import patch

import yandex_webmaster_analytics as yw


class YandexCollectorTests(unittest.TestCase):
    def test_sitemap_urls_from_local_repository(self):
        urls = yw.sitemap_urls()
        self.assertGreaterEqual(len(urls), 49)
        self.assertEqual(len(urls), len(set(urls)))
        self.assertIn(yw.SITE + "scada-hmi/", urls)

    def test_require_exact_verified_https_host(self):
        answer = {
            "hosts": [
                {"host_id": "http:dlvautomation.ru:80",
                 "ascii_host_url": "http://dlvautomation.ru/", "verified": True},
                {"host_id": "https:dlvautomation.ru:443",
                 "ascii_host_url": "https://dlvautomation.ru/", "verified": True,
                 "main_mirror": {"ascii_host_url": "https://dlvautomation.ru/"}},
            ]
        }
        with patch.object(yw, "request_yandex", side_effect=[
            {"user_id": 1234}, answer
        ]):
            base, primary = yw.get_verified_host({})
        self.assertTrue(primary)
        self.assertTrue(base.endswith("https%3Adlvautomation.ru%3A443"))

    def test_reject_unverified_site(self):
        answer = {"hosts": [
            {"host_id": "https:dlvautomation.ru:443",
             "ascii_host_url": yw.SITE, "verified": False}
        ]}
        with patch.object(yw, "request_yandex", side_effect=[
            {"user_id": 1234}, answer
        ]):
            with self.assertRaisesRegex(RuntimeError, "not verified"):
                yw.get_verified_host({})

    def test_sitemap_registration_is_idempotent(self):
        data = {"sitemaps": [{"sitemap_url": yw.SITEMAP}]}
        with patch.object(yw, "request_yandex", return_value=data) as call:
            status = yw.ensure_sitemap("/user/123/hosts/abc", {})
        self.assertEqual(status, "уже добавлен")
        self.assertEqual(call.call_count, 1)

    def test_sitemap_registration_if_missing(self):
        with patch.object(yw, "request_yandex", side_effect=[
            {"sitemaps": []}, {"sitemap_id": "abc"}
        ]) as call:
            status = yw.ensure_sitemap("/user/123/hosts/abc", {})
        self.assertEqual(status, "добавлен")
        self.assertEqual(call.call_count, 2)

    def test_aggregate_totals_by_day_not_by_query_subset(self):
        values = {"indicators": {
            "TOTAL_SHOWS": [
                {"date": "2026-10-21T00:00:00+03:00", "value": 10},
                {"date": "2026-10-22T00:00:00+03:00", "value": 30},
                {"date": "2026-10-24T00:00:00+03:00", "value": 99}],
            "TOTAL_CLICKS": [
                {"date": "2026-10-21T00:00:00+03:00", "value": 1},
                {"date": "2026-10-22T00:00:00+03:00", "value": 3}],
            "AVG_SHOW_POSITION": [
                {"date": "2026-10-21T00:00:00+03:00", "value": 5},
                {"date": "2026-10-22T00:00:00+03:00", "value": 25}],
        }}
        with patch.object(yw, "request_yandex", return_value=values):
            result = yw.site_totals("/base", {}, "2026-10-21", "2026-10-22")
        self.assertEqual(result, ["2026-10-21", "2026-10-22", 40, 4, 20, 2])

    def test_missing_total_data_is_not_reported_as_zero(self):
        with patch.object(yw, "request_yandex", return_value={"indicators": {}}):
            self.assertIsNone(yw.site_totals("/base", {}, "2026-10-21", "2026-10-22"))

    def test_priority_reindex_requires_explicit_manual_flag(self):
        with patch.dict(os.environ, {"DLV_YANDEX_RECRAWL": "false"}):
            with patch.object(yw, "request_yandex") as req:
                yw.maybe_reindex("/base", {}, yw.sitemap_urls())
                req.assert_not_called()

    def test_query_rows_match_existing_yandex_sheet_columns(self):
        with patch.object(yw, "request_yandex", return_value={"queries": [{
            "query_text": "программирование плк",
            "indicators": {"TOTAL_SHOWS": 2, "TOTAL_CLICKS": 1,
                           "AVG_SHOW_POSITION": 3, "AVG_CLICK_POSITION": 2}
        }]}):
            rows = yw.popular_queries("/base", {}, "2026-10-21", "2026-10-27")
        self.assertEqual(rows, [["2026-10-21", "2026-10-27", "программирование плк",
                                 2, 1, 3, 2]])


if __name__ == "__main__":
    unittest.main()
