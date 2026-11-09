"""Probe each OPML feed from this client; Miniflux errors are historical context only.

Policy: a 2xx response is healthy only with a complete, parseable RSS/RDF/Atom
feed body. Live 404/410 is gone (the only failing verdict); 403 or a recognizable
bot/CAPTCHA/JavaScript challenge is blocked-to-this-client, not dead. Timeouts,
connection failures, 429, 5xx, oversized bodies and other inconclusive
responses are unreachable now, never proof of retirement. Invalid 2xx XML/HTML
is reported separately and is not automatically gone. Follow redirects, read
at most 8 MiB, and retry transient transport errors, 429 and 5xx twice with
0.3/0.6 second backoff.
Each URL gets at most three requests, with 24 workers and 4s connect / 6s read
timeouts. --fail-on-dead fails only on live 404/410. --base-opml marks new feeds
in the report; --min-error-count filters optional Miniflux warning annotations.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

FEEDS_XML = Path(__file__).resolve().parent.parent / "feeds.xml"
DEFAULT_MIN_ERROR_COUNT = 3
WORKERS = 24
MAX_ATTEMPTS = 3
MAX_BODY = 8 * 1024 * 1024
HEADERS = {
    "User-Agent": "infosec-opml-feed-health/1.0 (+https://github.com/phretor/infosec-opml)",
    "Accept": (
        "application/atom+xml, application/rss+xml, application/rdf+xml, "
        "application/xml, text/xml; q=0.9, */*; q=0.5"
    ),
}
TIMEOUT = httpx.Timeout(6.0, connect=4.0, pool=4.0)
Verdict = Literal["healthy", "gone", "blocked-to-this-client", "unreachable", "invalid"]


@dataclass(frozen=True)
class FeedRow:
    name: str
    xml_url: str
    folder: str


@dataclass(frozen=True)
class MinifluxStatus:
    disabled: bool
    parsing_error_count: int
    parsing_error_message: str


@dataclass(frozen=True)
class Probe:
    verdict: Verdict
    status_code: int | None
    final_url: str
    detail: str = ""
    attempts: int = 1


def parse_feeds(path: Path) -> list[FeedRow]:
    root = ET.parse(path).getroot()
    body = root.find("body")
    if body is None:
        return []
    return [
        FeedRow(feed.get("text", ""), feed.get("xmlUrl", ""), folder.get("text", ""))
        for folder in body
        for feed in folder
        if feed.get("type") == "rss" and feed.get("xmlUrl")
    ]


def fetch_miniflux_feeds(base_url: str, token: str) -> dict[str, MinifluxStatus]:
    """Optional diagnostic data; failure never changes a live probe verdict."""
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        response = client.get(base_url.rstrip("/") + "/v1/feeds", headers={"X-Auth-Token": token})
        response.raise_for_status()
        return {
            row["feed_url"]: MinifluxStatus(
                bool(row.get("disabled", False)),
                int(row.get("parsing_error_count", 0)),
                str(row.get("parsing_error_message", "")),
            )
            for row in response.json()
        }


def _feed_xml(body: bytes) -> bool:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return False
    name = root.tag.rsplit("}", 1)[-1].lower()
    children = {child.tag.rsplit("}", 1)[-1].lower() for child in root}
    if name == "rss":
        return any(child.tag.rsplit("}", 1)[-1].lower() == "channel" and
                   any(item.tag.rsplit("}", 1)[-1].lower() in {"title", "item"} for item in child)
                   for child in root)
    if name in {"feed", "rdf"}:
        return bool(children & ({"title", "entry"} if name == "feed" else {"channel", "item"}))
    return False


def _challenge(body: bytes) -> bool:
    text = body[:65536].lower()
    return any(marker in text for marker in (
        b"cf-chl-", b"cloudflare ray id", b"checking your browser",
        b"verify you are human", b"captcha", b"javascript challenge",
        b"enable javascript to continue", b"just a moment...",
    ))


def probe_feed(url: str, client: httpx.Client, sleep=time.sleep) -> Probe:
    """Fetch one URL within a three-attempt budget; keep its last live evidence."""
    parsed_url = httpx.URL(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.host:
        return Probe("invalid", None, url, "not an HTTP URL")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        status: int | None = None
        final = url
        try:
            with client.stream("GET", url, headers=HEADERS, follow_redirects=True) as response:
                status = response.status_code
                final = str(response.url)
                # Only read bodies relevant to feed validity / challenge detection.
                body = b""
                if status == 403 or 200 <= status < 300 or status == 429 or status >= 500:
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        chunks.extend(chunk[: max(0, MAX_BODY + 1 - len(chunks))])
                        if len(chunks) > MAX_BODY:
                            break
                    body = bytes(chunks)
                if status in {404, 410}:
                    return Probe("gone", status, final, attempts=attempt)
                if status == 403:
                    return Probe("blocked-to-this-client", status, final, attempts=attempt)
                if 200 <= status < 300:
                    if len(body) > MAX_BODY:
                        return Probe(
                            "unreachable", status, final, "body exceeds 8 MiB cap", attempt,
                        )
                    if _feed_xml(body):
                        return Probe("healthy", status, final, attempts=attempt)
                    challenge = _challenge(body)
                    return Probe(
                        "blocked-to-this-client" if challenge else "invalid",
                        status, final,
                        "challenge page" if challenge else "not a parseable RSS/Atom feed",
                        attempt,
                    )
                if _challenge(body):
                    return Probe("blocked-to-this-client", status, final, attempts=attempt)
                detail = f"HTTP {status}"
                retry = status == 429 or status >= 500
        except httpx.RequestError as exc:
            detail = type(exc).__name__
            retry = True
        except (ValueError, ET.ParseError) as exc:
            return Probe("invalid", None, url, type(exc).__name__, attempt)
        if not retry or attempt == MAX_ATTEMPTS:
            return Probe("unreachable", status, final, detail, attempt)
        sleep(0.3 * 2 ** (attempt - 1))
    raise AssertionError("attempt budget exhausted")


def probe_feeds(feeds: list[FeedRow], client: httpx.Client | None = None,
                workers: int = WORKERS) -> dict[str, Probe]:
    """One shared thread-safe client, bounded workers, one probe per distinct URL."""
    urls = list(dict.fromkeys(feed.xml_url for feed in feeds))
    if client is None:
        with httpx.Client(timeout=TIMEOUT, limits=httpx.Limits(max_connections=workers),
                          follow_redirects=True) as owned:
            return probe_feeds(feeds, owned, workers)

    def safe_probe(url: str) -> Probe:
        try:
            return probe_feed(url, client)
        except Exception as exc:  # noqa: BLE001 - isolate unexpected per-feed failures
            return Probe("unreachable", None, url, type(exc).__name__)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip(urls, pool.map(safe_probe, urls)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe RSS/Atom feed URLs from this client")
    parser.add_argument(
        "--fail-on-dead", action="store_true", help="Fail on live HTTP 404/410 only",
    )
    parser.add_argument("--base-opml", type=Path, help="Mark feeds new relative to the PR base")
    parser.add_argument("--min-error-count", type=int, default=DEFAULT_MIN_ERROR_COUNT,
                        help="Show optional Miniflux warnings at or above this count (default: 3)")
    args = parser.parse_args()
    if args.min_error_count < 1:
        parser.error("--min-error-count must be positive")
    feeds = parse_feeds(FEEDS_XML)
    new_urls = set()
    if args.base_opml:
        old_urls = {feed.xml_url for feed in parse_feeds(args.base_opml)}
        new_urls = {feed.xml_url for feed in feeds} - old_urls
    miniflux: dict[str, MinifluxStatus] = {}
    if os.environ.get("MINIFLUX_URL") and os.environ.get("MINIFLUX_TOKEN"):
        try:
            miniflux = fetch_miniflux_feeds(os.environ["MINIFLUX_URL"],
                                             os.environ["MINIFLUX_TOKEN"])
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            print(f"Miniflux diagnostics unavailable: {exc}", file=sys.stderr)
    probes = probe_feeds(feeds)
    buckets: dict[Verdict, list[FeedRow]] = {key: [] for key in
        ("healthy", "gone", "blocked-to-this-client", "unreachable", "invalid")}
    for feed in feeds:
        buckets[probes[feed.xml_url].verdict].append(feed)
    print(f"Feeds: {len(feeds)} in feeds.xml; {len(miniflux)} Miniflux diagnostics")
    print("Results: " + ", ".join(f"{len(rows)} {verdict}" for verdict, rows in buckets.items()))
    for verdict, rows in buckets.items():
        if not rows or verdict == "healthy":
            continue
        print(f"\n{verdict.upper()} ({len(rows)})")
        for feed in sorted(rows, key=lambda item: (item.folder, item.name)):
            result = probes[feed.xml_url]
            status = result.status_code if result.status_code is not None else "no response"
            print(f"  [{verdict}] {feed.xml_url} | HTTP {status} | final: {result.final_url}"
                  f" | attempts: {result.attempts} | {feed.name} ({feed.folder})")
            if result.detail:
                print(f"    Evidence: {result.detail}")
            previous = miniflux.get(feed.xml_url)
            if previous and (
                previous.parsing_error_count >= args.min_error_count or previous.disabled
            ):
                print(f"    Miniflux history: {previous.parsing_error_count} errors"
                      f"{' (disabled)' if previous.disabled else ''}; "
                      f"{previous.parsing_error_message[:120]}")
            if feed.xml_url in new_urls:
                print("    New in PR base comparison")
    if args.fail_on_dead and buckets["gone"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
