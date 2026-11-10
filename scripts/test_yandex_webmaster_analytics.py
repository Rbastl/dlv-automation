#!/usr/bin/env python3
"""Offline regression tests: never contact Yandex or private Google Sheets."""
import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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

    def test_optional_404_retains_each_documented_reason(self):
        for code in ("HOST_NOT_INDEXED", "HOST_NOT_LOADED"):
            with self.subTest(code=code):
                response = Mock(status_code=404)
                response.json.return_value = {"error_code": code}
                requests = SimpleNamespace(
                    request=Mock(return_value=response),
                    exceptions=SimpleNamespace(ConnectionError=ConnectionError,
                                               Timeout=TimeoutError),
                )
                status = {}
                with patch.dict(sys.modules, {"requests": requests}):
                    result = yw.request_yandex(
                        "GET", "/base", {}, "pages in search",
                        optional=True, availability=status)
                self.assertIsNone(result)
                self.assertEqual(status, {"pages in search": code})
                self.assertEqual(requests.request.call_count, 1)

    def test_auth_error_is_not_treated_as_optional_absence(self):
        response = Mock(status_code=403)
        response.json.return_value = {"error_code": "INVALID_USER_ID"}
        requests = SimpleNamespace(
            request=Mock(return_value=response),
            exceptions=SimpleNamespace(ConnectionError=ConnectionError,
                                       Timeout=TimeoutError),
        )
        status = {}
        with patch.dict(sys.modules, {"requests": requests}):
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                yw.request_yandex("GET", "/base", {}, "pages in search",
                                  optional=True, availability=status)
        self.assertEqual(status, {})

    def test_empty_successful_history_is_distinct_from_measured_zero(self):
        for value, expected, code in (([], "", "EMPTY"),
                                     ([{"date": "2026-10-22", "value": 0}],
                                      0, "OK")):
            with self.subTest(value=value):
                response = Mock(status_code=200)
                response.json.return_value = {"history": value}
                requests = SimpleNamespace(
                    request=Mock(return_value=response),
                    exceptions=SimpleNamespace(ConnectionError=ConnectionError,
                                               Timeout=TimeoutError),
                )
                status = {}
                with patch.dict(sys.modules, {"requests": requests}):
                    result = yw.indexed_pages("/base", {}, "2026-10-21",
                                              "2026-10-22", status)
                self.assertEqual(result, expected)
                self.assertEqual(status, {"pages in search": code})

    def test_empty_total_response_has_its_own_status(self):
        status = {}
        with patch.object(yw, "request_yandex", return_value={"indicators": {}}):
            self.assertIsNone(yw.site_totals("/base", {}, "2026-10-21",
                                             "2026-10-22", status))
        self.assertEqual(status, {"total search history": "EMPTY"})

    def test_zero_totals_are_preserved_as_actual_measurements(self):
        values = {"indicators": {
            "TOTAL_SHOWS": [{"date": "2026-10-21", "value": 0}],
            "TOTAL_CLICKS": [{"date": "2026-10-21", "value": 0}],
        }}
        with patch.object(yw, "request_yandex", return_value=values):
            result = yw.site_totals("/base", {}, "2026-10-21", "2026-10-22")
        self.assertEqual(result, ["2026-10-21", "2026-10-22", 0, 0, "", 1])

    def test_empty_popular_queries_are_not_reported_as_received_data(self):
        status = {}
        with patch.object(yw, "request_yandex", return_value={"queries": []}):
            self.assertEqual(yw.popular_queries("/base", {}, "2026-10-21",
                                                "2026-10-22", status), [])
        self.assertEqual(status, {"popular queries": "EMPTY"})

    def test_private_comment_distinguishes_three_endpoint_outcomes(self):
        comment = yw.availability_comment({
            "pages in search": "HOST_NOT_INDEXED",
            "total search history": "EMPTY",
            "popular queries": "STORED",
        })
        self.assertIn("HOST_NOT_INDEXED", comment)
        self.assertIn("HTTP 200", comment)
        self.assertIn("период уже сохранён", comment)

    def test_priority_reindex_requires_explicit_manual_flag(self):
        with patch.dict(os.environ, {"DLV_YANDEX_RECRAWL": "false"}):
            with patch.object(yw, "request_yandex") as req:
                yw.maybe_reindex("/base", {}, yw.sitemap_urls())
                req.assert_not_called()

    def test_recrawl_does_not_duplicate_already_queued_urls(self):
        wanted = {yw.SITE + path: "IN_PROGRESS" for path in yw.PRIORITY_PATHS}
        with patch.dict(os.environ, {"DLV_YANDEX_RECRAWL": "true"}):
            with patch.object(yw, "recrawl_queue", return_value=wanted):
                with patch.object(yw, "request_yandex",
                                  return_value={"quota_remainder": 4}) as req:
                    with patch.object(yw, "report"):
                        yw.maybe_reindex("/base", {}, yw.sitemap_urls())
                    self.assertEqual(req.call_count, 1)
                    self.assertEqual(req.call_args.args[0], "GET")

    def test_no_post_when_quota_is_exhausted(self):
        with patch.dict(os.environ, {"DLV_YANDEX_RECRAWL": "true"}):
            with patch.object(yw, "recrawl_queue", return_value={}):
                with patch.object(yw, "request_yandex",
                                  return_value={"quota_remainder": 0}) as req:
                    with patch.object(yw, "report"):
                        yw.maybe_reindex("/base", {}, yw.sitemap_urls())
                    self.assertEqual(req.call_count, 1)

    def test_uncertain_post_is_not_replayed(self):
        with patch.dict(os.environ, {"DLV_YANDEX_RECRAWL": "true"}):
            with patch.object(yw, "recrawl_queue", side_effect=[{}, {}]):
                with patch.object(yw, "request_yandex", side_effect=[
                    {"quota_remainder": 1}, RuntimeError("gateway 504")
                ]) as req:
                    with self.assertRaisesRegex(RuntimeError, "no automatic POST retry"):
                        yw.maybe_reindex("/base", {}, yw.sitemap_urls())
                    self.assertEqual(req.call_count, 2)


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
