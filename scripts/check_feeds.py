"""Classify RSS/Atom feed health using Miniflux as the source of truth.

Miniflux already polls every feed on its own schedule and tracks parsing errors
with a stable `parsing_error_count` field. We read that view instead of probing
URLs from the CI runner, which was unreliable because many hosts return 4xx/429
to generic cloud IPs for feeds that are perfectly healthy from Miniflux's end.
"""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

FEEDS_XML = Path(__file__).resolve().parent.parent / "feeds.xml"
DEFAULT_MIN_ERROR_COUNT = 3
HTTP_TIMEOUT = 30.0

Verdict = Literal["ok", "transient", "dead"]


@dataclass(frozen=True)
class FeedRow:
    """A feed from feeds.xml, independent of Miniflux knowledge."""

    name: str
    xml_url: str
    folder: str


@dataclass(frozen=True)
class MinifluxStatus:
    """Just the health-relevant subset of Miniflux's feed record."""

    disabled: bool
    parsing_error_count: int
    parsing_error_message: str


@dataclass(frozen=True)
class ClassifiedFeed:
    """Classification outcome for one feed in feeds.xml."""

    feed: FeedRow
    verdict: Verdict
    status: MinifluxStatus | None  # None iff feed is missing from Miniflux


def parse_feeds(path: Path) -> list[FeedRow]:
    """Parse feeds.xml into FeedRow objects, flat list across all folders."""
    tree = ET.parse(path)
    rows: list[FeedRow] = []
    body = tree.getroot().find("body")
    if body is None:
        return rows
    for folder in body:
        folder_name = folder.get("text", "")
        for feed in folder:
            if feed.get("type") == "rss" and feed.get("xmlUrl"):
                rows.append(
                    FeedRow(
                        name=feed.get("text", ""),
                        xml_url=feed.get("xmlUrl", ""),
                        folder=folder_name,
                    )
                )
    return rows


def fetch_miniflux_feeds(
    base_url: str, api_token: str, client: httpx.Client | None = None
) -> dict[str, MinifluxStatus]:
    """GET /v1/feeds, returning {feed_url: MinifluxStatus}.

    Takes an optional httpx client so tests can inject MockTransport.
    """
    url = base_url.rstrip("/") + "/v1/feeds"
    headers = {"X-Auth-Token": api_token}
    owned = client is None
    if client is None:
        client = httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True)
    try:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if owned:
            client.close()
    return {
        row["feed_url"]: MinifluxStatus(
            disabled=bool(row.get("disabled", False)),
            parsing_error_count=int(row.get("parsing_error_count", 0)),
            parsing_error_message=str(row.get("parsing_error_message", "")),
        )
        for row in payload
    }


def classify(status: MinifluxStatus | None, min_error_count: int) -> Verdict:
    """Classify one feed given its Miniflux status (or None if missing)."""
    if status is None:
        return "dead"
    if status.disabled:
        return "dead"
    if status.parsing_error_count >= min_error_count:
        return "dead"
    if status.parsing_error_count > 0:
        return "transient"
    return "ok"


def classify_feeds(
    feeds: list[FeedRow],
    miniflux_by_url: dict[str, MinifluxStatus],
    min_error_count: int,
) -> list[ClassifiedFeed]:
    """Apply classify() to each feed in feeds.xml."""
    return [
        ClassifiedFeed(
            feed=f,
            verdict=classify(miniflux_by_url.get(f.xml_url), min_error_count),
            status=miniflux_by_url.get(f.xml_url),
        )
        for f in feeds
    ]


def print_section(title: str, entries: list[ClassifiedFeed]) -> None:
    if not entries:
        return
    entries = sorted(entries, key=lambda e: (e.feed.folder, e.feed.name))
    print("=" * 80)
    print(title)
    print("=" * 80)
    for e in entries:
        label = e.verdict
        print(f"  [{label:>12}]  {e.feed.xml_url}")
        print(f"                 Feed: {e.feed.name}")
        print(f"                 Folder: {e.feed.folder}")
        if e.status is None:
            print("                 Miniflux: feed not found")
        else:
            count = e.status.parsing_error_count
            msg = e.status.parsing_error_message.strip().replace("\n", " ")
            msg_snippet = msg[:120] + ("…" if len(msg) > 120 else "")
            disabled_tag = " (disabled)" if e.status.disabled else ""
            print(f"                 Miniflux: {count} error(s){disabled_tag}")
            if msg_snippet:
                print(f"                 Message: {msg_snippet}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify RSS/Atom feed health using Miniflux's API"
    )
    parser.add_argument(
        "--fail-on-dead",
        action="store_true",
        help="Exit non-zero if any feed in feeds.xml is classified dead",
    )
    parser.add_argument(
        "--min-error-count",
        type=int,
        default=DEFAULT_MIN_ERROR_COUNT,
        help=(
            "Parsing-error threshold at which a feed is dead "
            f"(default: {DEFAULT_MIN_ERROR_COUNT})"
        ),
    )
    args = parser.parse_args()

    if not FEEDS_XML.exists():
        print(f"error: {FEEDS_XML} not found", file=sys.stderr)
        sys.exit(1)

    base = os.environ.get("MINIFLUX_URL")
    token = os.environ.get("MINIFLUX_TOKEN")
    if not base or not token:
        print(
            "error: MINIFLUX_URL and MINIFLUX_TOKEN must be set",
            file=sys.stderr,
        )
        sys.exit(2)

    feeds = parse_feeds(FEEDS_XML)
    miniflux = fetch_miniflux_feeds(base, token)
    classified = classify_feeds(feeds, miniflux, args.min_error_count)

    buckets: dict[Verdict, list[ClassifiedFeed]] = {"ok": [], "transient": [], "dead": []}
    for c in classified:
        buckets[c.verdict].append(c)

    print(f"Feeds: {len(feeds)} in feeds.xml, {len(miniflux)} in Miniflux\n")
    print(
        f"Results: {len(buckets['ok'])} OK, "
        f"{len(buckets['dead'])} dead, "
        f"{len(buckets['transient'])} transient "
        f"(threshold: parsing_error_count >= {args.min_error_count})\n"
    )

    print_section(
        "DEAD FEEDS (disabled, over error threshold, or missing from Miniflux)",
        buckets["dead"],
    )
    print_section(
        f"TRANSIENT ERRORS (parsing_error_count 1-{args.min_error_count - 1})",
        buckets["transient"],
    )

    if args.fail_on_dead and buckets["dead"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
