#!/usr/bin/env python3
"""Read-only layered HTTPS reachability probe for DLV's own production host.

Separates DNS, TCP/443, TLS certificate/handshake and HTTP response failures.
Uses a single short direct connection per endpoint.  Never changes DNS or
hosting settings, never sends credentials, and never touches third-party sites.
Diagnostic failures are reported, not treated as Googlebot crawl failures.
"""
from __future__ import annotations

import json
import os
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path

HOST = "dlvautomation.ru"
PORT = 443
TIMEOUT_SECONDS = 6
PATHS = ("/robots.txt", "/dlv-deploy-revision.txt")
OUT = Path("seo-reports/https-layer.json")


def error_kind(error: Exception) -> str:
    if isinstance(error, socket.gaierror):
        return "dns_resolution"
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(error, ssl.SSLCertVerificationError):
        return "tls_certificate"
    if isinstance(error, ssl.SSLError):
        return "tls_handshake"
    if isinstance(error, ConnectionRefusedError):
        return "connection_refused"
    if isinstance(error, ConnectionResetError):
        return "connection_reset"
    if isinstance(error, OSError):
        return "network_os_error"
    return "unexpected"


def status_code_from_bytes(data: bytes) -> int | None:
    # We explicitly request HTTP/1.1; TLS ALPN negotiation is not needed.
    head = data.split(b"\r\n", 1)[0]
    match = re.fullmatch(rb"HTTP/1\.[01] ([1-5][0-9]{2})[ -~]*", head)
    return int(match.group(1)) if match else None


def get_ip_endpoints() -> list[dict]:
    result = []
    for family, socktype, _proto, _canon, sockaddr in socket.getaddrinfo(
        HOST, PORT, type=socket.SOCK_STREAM
    ):
        if socktype != socket.SOCK_STREAM:
            continue
        ip = sockaddr[0]
        if any(item["ip"] == ip for item in result):
            continue
        result.append({
            "family": "IPv4" if family == socket.AF_INET else "IPv6",
            "ip": ip,
            "_family": family,
            "_address": sockaddr,
        })
    # Prevent broad IP probing; at most one IPv4 and one IPv6 endpoint.
    subset = []
    for kind in ("IPv4", "IPv6"):
        item = next((x for x in result if x["family"] == kind), None)
        if item:
            subset.append(item)
    return subset


def probe(endpoint: dict, path: str) -> dict:
    item = {
        "family": endpoint["family"], "ip": endpoint["ip"],
        "path": path, "tcp": "not_started", "tls": "not_started",
        "http": "not_started",
    }
    started = time.monotonic()
    stage = "tcp"
    try:
        with socket.socket(endpoint["_family"], socket.SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT_SECONDS)
            sock.connect(endpoint["_address"])
            item["tcp"] = "ok"
            item["tcp_ms"] = round((time.monotonic() - started) * 1000)
            stage = "tls"
            with ssl.create_default_context().wrap_socket(
                sock, server_hostname=HOST
            ) as secured:
                item["tls"] = "ok"
                item["tls_ms"] = round((time.monotonic() - started) * 1000)
                stage = "http"
                secured.settimeout(TIMEOUT_SECONDS)
                request = (
                    f"GET {path} HTTP/1.1\r\n"
                    f"Host: {HOST}\r\n"
                    "User-Agent: DLVAutomationLayerProbe/1.0\r\n"
                    "Accept: text/plain,*/*\r\n"
                    "Connection: close\r\n\r\n"
                )
                secured.sendall(request.encode("ascii"))
                data = secured.recv(8192)
                item["http_status"] = status_code_from_bytes(data)
                item["http"] = "ok" if item["http_status"] else "invalid_status"
                item["response_ms"] = round((time.monotonic() - started) * 1000)
    except Exception as exc:
        item[stage] = error_kind(exc)
        item["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    return item


def run() -> dict:
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": HOST,
        "port": PORT,
        "note": "Direct TCP/TLS probe from one GitHub runner. A failing probe does "
                "not prove Googlebot or YandexBot was blocked.",
        "proxy_env_present": {
            "http_proxy": bool(os.getenv("HTTP_PROXY") or os.getenv("http_proxy")),
            "https_proxy": bool(os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")),
        },
        "dns": [],
        "checks": [],
    }
    try:
        endpoints = get_ip_endpoints()
        report["dns"] = [
            {"family": e["family"], "ip": e["ip"]} for e in endpoints
        ]
    except Exception as exc:
        report["dns_error"] = error_kind(exc)
        endpoints = []
    for endpoint in endpoints:
        for path in PATHS:
            report["checks"].append(probe(endpoint, path))
    return report


def main() -> int:
    report = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    # Safe public summary, without response bodies, auth headers or credentials.
    print("DLV HTTPS layers: DNS =", report["dns"] or report.get("dns_error"))
    for item in report["checks"]:
        print(
            "DLV HTTPS layers:", item["family"], item["path"],
            "TCP=" + item["tcp"], "TLS=" + item["tls"],
            "HTTP=" + str(item.get("http_status", item["http"])),
            "elapsed_ms=" + str(item.get("response_ms", item.get("elapsed_ms", ""))),
        )
    # Do not replace the existing full site audit's true failure status.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
