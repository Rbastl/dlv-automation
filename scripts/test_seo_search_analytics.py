"""Offline regression checks: no Google API, private credentials or live writes."""
import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import seo_search_analytics as seo


def answer(data, status=200):
    response = Mock(status_code=status)
    response.json.return_value = data
    return response


def metric(url, impressions=7):
    return {"keys": [url], "clicks": 1, "impressions": impressions,
            "ctr": 1 / impressions, "position": 8}


class PageReportTests(unittest.TestCase):
    def setUp(self):
        self.period = ("2026-10-01", "2026-10-07")
        self.session = Mock()
        self.console = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.console)
        self.redirect.__enter__()

    def tearDown(self):
        self.redirect.__exit__(None, None, None)

    def test_owned_hosts_preserve_http_https_and_www(self):
        for scheme in ("http", "https"):
            for host in (seo.SITE_HOST, "www." + seo.SITE_HOST):
                self.assertTrue(seo.owned_page_url(f"{scheme}://{host}/path/?x=1"))
        for url in (None, "", "/local/", "ftp://dlvautomation.ru/",
                    "https://dlvautomation.ru.evil.invalid/",
                    "https://dlvautomation.ru@evil.invalid/",
                    "https://evil.invalid@dlvautomation.ru/",
                    "https://notdlvautomation.ru/", "http://[broken"):
            self.assertFalse(seo.owned_page_url(url), url)

    def test_existing_period_gets_missing_variants_once_without_rewriting(self):
        secure = "https://dlvautomation.ru/service/"
        plain = "http://dlvautomation.ru/service/"
        www = "https://www.dlvautomation.ru/service/?a=1"
        existing = {(*self.period, secure)}
        self.session.post.return_value = answer({"rows": [
            metric(secure), metric(plain), metric(www), metric(plain),
            metric("https://foreign.invalid/")]})
        with patch.object(seo, "append_private", return_value=True) as append:
            seo.reconcile_google_pages(self.session, "endpoint", self.period, "stamp", existing)
            rows = append.call_args.args[2]
            self.assertEqual([r[2] for r in rows], [plain, www])
            self.assertEqual(rows[0][3:7], [1, 7, 1 / 7, 8])
            self.assertIn((*self.period, plain), existing)
            self.assertNotIn(plain, self.console.getvalue())
            append.reset_mock()
            seo.reconcile_google_pages(self.session, "endpoint", self.period, "later", existing)
            self.assertEqual(append.call_args.args[2], [])

    def test_pagination_keeps_later_rows(self):
        urls = [f"http://dlvautomation.ru/{x}/" for x in range(3)]
        self.session.post.side_effect = [
            answer({"rows": [metric(urls[0]), metric(urls[1])]}),
            answer({"rows": [metric(urls[2])]}),
        ]
        with patch.object(seo, "PAGE_REPORT_LIMIT", 2), patch.object(seo, "append_private", return_value=True) as append:
            seo.reconcile_google_pages(self.session, "endpoint", self.period, "stamp", set())
            self.assertEqual([c.kwargs["json"]["startRow"] for c in self.session.post.call_args_list], [0, 2])
            self.assertEqual([r[2] for r in append.call_args.args[2]], urls)

    def test_later_api_page_failure_writes_nothing(self):
        self.session.post.side_effect = [answer({"rows": [metric("http://dlvautomation.ru/a/")]}), answer({}, 503)]
        with patch.object(seo, "PAGE_REPORT_LIMIT", 1), patch.object(seo, "append_private") as append:
            with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
                seo.reconcile_google_pages(self.session, "endpoint", self.period, "stamp", set())
            append.assert_not_called()
        self.assertNotIn("http://", self.console.getvalue())

    def test_repair_windows_are_bounded_and_validate_dates(self):
        existing = {(start, end, "https://dlvautomation.ru/") for start, end in [
            ("2026-09-30", "2026-10-06"), ("2026-09-29", "2026-10-05"),
            ("2026-09-28", "2026-10-04"), ("2026-09-27", "2026-10-03"),
            ("2026-08-01", "2026-08-07"), ("2026-10-08", "2026-10-14"),
            ("2026-09-29", "2026-10-04"), ("bad", "dates"), self.period]}
        windows = seo.page_periods_to_repair(self.period, existing)
        self.assertEqual(windows, [self.period, ("2026-09-30", "2026-10-06"),
                                  ("2026-09-29", "2026-10-05"), ("2026-09-28", "2026-10-04")])
        with self.assertRaises(ValueError):
            seo.page_periods_to_repair(("2026-10-01", "2026-10-08"), existing)

    def test_stored_keys_ignore_short_and_foreign_rows(self):
        wanted = (*self.period, "http://www.dlvautomation.ru/a/")
        self.session.get.return_value = answer({"values": [list(wanted), list(wanted),
            ["header"], [*self.period, "https://foreign.invalid/"]]})
        self.assertEqual(seo.stored_page_keys(self.session), {wanted})

    def test_summary_skip_does_not_skip_existing_page_period(self):
        existing = {(*self.period, "https://dlvautomation.ru/")}
        with patch.object(seo, "already_collected", return_value=True), patch.object(seo, "stored_page_keys", return_value=existing), patch.object(seo, "reconcile_google_pages") as reconcile:
            seo.google_summary_and_pages(self.session, "endpoint", self.period, "stamp")
            reconcile.assert_called_once_with(self.session, "endpoint", self.period, "stamp", existing)


if __name__ == "__main__":
    unittest.main()
