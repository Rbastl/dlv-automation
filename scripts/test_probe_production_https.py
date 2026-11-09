"""Deterministic tests of the read-only Timeweb layer probe. No internet."""
import socket
import ssl
import unittest
from unittest.mock import patch

import probe_production_https as p


class TimewebProbeTests(unittest.TestCase):
    def test_http_status_ok(self):
        self.assertEqual(p.status_code_from_bytes(b"HTTP/1.1 200 OK\r\nServer: nginx\r\n"), 200)
        self.assertEqual(p.status_code_from_bytes(b"HTTP/1.0 503 Service Unavailable\r\n"), 503)

    def test_http_status_invalid(self):
        self.assertIsNone(p.status_code_from_bytes(b""))
        self.assertIsNone(p.status_code_from_bytes(b"Not HTTP"))
        self.assertIsNone(p.status_code_from_bytes(b"HTTP/2 200\r\n"))

    def test_error_taxonomy(self):
        self.assertEqual(p.error_kind(socket.gaierror("DNS")), "dns_resolution")
        self.assertEqual(p.error_kind(socket.timeout()), "timeout")
        self.assertEqual(p.error_kind(ssl.SSLError("TLS")), "tls_handshake")
        self.assertEqual(p.error_kind(ssl.SSLCertVerificationError("invalid")), "tls_certificate")
        self.assertEqual(p.error_kind(ConnectionRefusedError()), "connection_refused")
        self.assertEqual(p.error_kind(ConnectionResetError()), "connection_reset")
        self.assertEqual(p.error_kind(OSError("generic")), "network_os_error")

    def test_http_canonical_redirect_classification(self):
        self.assertEqual(
            p.http_redirect_result(301, "https://dlvautomation.ru/", "/"),
            "permanent_https_canonical",
        )
        self.assertEqual(
            p.http_redirect_result(308,
                "https://dlvautomation.ru/en/control-system-modernization/",
                "/en/control-system-modernization/"),
            "permanent_https_canonical",
        )
        self.assertEqual(
            p.http_redirect_result(200, None, "/"), "http_200_unredirected",
        )
        self.assertEqual(
            p.http_redirect_result(301, "http://dlvautomation.ru/", "/"),
            "redirect_to_different_target",
        )
        self.assertEqual(
            p.http_redirect_result(302, "https://dlvautomation.ru/", "/"),
            "temporary_or_other_status",
        )
        self.assertEqual(
            p.http_redirect_result(301, "https://other.example/", "/"),
            "redirect_to_different_target",
        )

    def test_http_location_parser(self):
        self.assertEqual(
            p.header_location(b"HTTP/1.1 301 Moved Permanently\r\n"
                              b"Content-Type: text/html\r\n"
                              b"Location: https://dlvautomation.ru/\r\n\r\n"),
            "https://dlvautomation.ru/",
        )
        self.assertIsNone(p.header_location(b"HTTP/1.1 200 OK\r\n\r\n"))

    def test_deduplicate_ipv4_ipv6(self):
        responses = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 443, 0, 0)),
        ]
        with patch.object(p.socket, "getaddrinfo", return_value=responses):
            got = p.get_ip_endpoints()
        self.assertEqual([x["family"] for x in got], ["IPv4", "IPv6"])
        self.assertEqual(len(got), 2)

    def test_missing_dns_is_reported_not_fatal(self):
        with patch.object(p, "get_ip_endpoints", side_effect=socket.gaierror("no host")):
            result = p.run()
        self.assertEqual(result["dns_error"], "dns_resolution")
        self.assertEqual(result["checks"], [])

    def test_probe_does_not_call_network_without_endpoints(self):
        with patch.object(p, "get_ip_endpoints", return_value=[]):
            with patch.object(p, "probe") as probe:
                result = p.run()
        probe.assert_not_called()
        self.assertEqual(result["dns"], [])


if __name__ == "__main__":
    unittest.main()
