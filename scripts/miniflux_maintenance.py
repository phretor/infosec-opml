"""One-time, explicitly approved Miniflux feed repair; dry run by default.

The fixed URL list comes from the verified 2026-11-01 feed-health findings.
No OPML edits are made here: Miniflux is the source of truth.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Literal

import httpx

from scripts.check_feeds import HTTP_TIMEOUT

Action = Literal["repoint", "delete"]


@dataclass(frozen=True)
class Repair:
    action: Action
    old: str
    reason: str
    new: str | None = None


# Project Zero's first alias survives and is pointed to the canonical feed; the
# second is removed. Jorenar likewise keeps one of its two broken old URLs.
REPAIRS = (
    Repair(
        "repoint",
        "https://googleprojectzero.blogspot.com/feeds/posts/default?alt=rss",
        "Project Zero canonical feed",
        "https://projectzero.google/feed.xml",
    ),
    Repair(
        "delete",
        "https://googleprojectzero.blogspot.com/feeds/posts/default",
        "duplicate Project Zero alias",
    ),
    Repair("delete", "https://blog.trailofbits.com/feed/", "duplicate redirect alias"),
    Repair("delete", "https://blog.sonarsource.com/rss.xml", "duplicate redirect alias"),
    Repair("delete", "https://www.wiz.io/blog/rss/", "duplicate redirect alias"),
    Repair("delete", "https://blog.nviso.eu/feed", "duplicate redirect alias"),
    Repair("delete", "https://www.welivesecurity.com/feed", "duplicate redirect alias"),
    Repair("delete", "https://www.technologyreview.com/stories.rss", "duplicate redirect alias"),
    Repair(
        "repoint",
        "https://blog.exatrack.com/index.xml",
        "moved feed (verified)",
        "https://exatrack.com/rss.xml",
    ),
    Repair(
        "repoint",
        "https://haxrob.net/rss/",
        "moved feed (verified; dormant)",
        "https://haxrob.net/rss.xml",
    ),
    Repair(
        "repoint",
        "https://codeneverdies.github.io/feed.xml",
        "moved feed (verified)",
        "https://codeneverdies.github.io/index.xml",
    ),
    Repair(
        "repoint",
        "https://riccardoancarani.github.io/feed.xml",
        "moved feed (verified; dormant)",
        "https://riccardoancarani.github.io/index.xml",
    ),
    Repair(
        "repoint",
        "https://www.sentinelone.com/feed/",
        "moved feed (verified)",
        "https://www.sentinelone.com/blog/feed/",
    ),
    Repair(
        "repoint",
        "https://www.techtarget.com/searchsecurity/rss/Security-Wire-Daily-News.xml",
        "moved feed (verified; replacement is site-wide news)",
        "https://www.techtarget.com/feeds/news/",
    ),
    Repair(
        "repoint",
        "https://jorenar.com/blog/feed.xml",
        "moved feed (verified)",
        "https://jorenar.com/feed.xml",
    ),
    Repair(
        "delete", "https://jorenar.com/blog/feed", "duplicate Jorenar entry; survivor is repointed"
    ),
    Repair(
        "repoint",
        "https://feeds2.feedburner.com/thenextweb",
        "moved feed (verified)",
        "https://thenextweb.com/feed",
    ),
    Repair("delete", "https://comsecuris.com/index.xml", "site has no live feed"),
    Repair("delete", "https://hakaisecurity.io/feed/", "site has no live feed"),
    Repair("delete", "https://www.legitsecurity.com/blog/rss.xml", "site has no live feed"),
    Repair("delete", "https://hadess.io/feed/", "site has no live feed"),
)


def run(client: httpx.Client, base_url: str, token: str, *, apply: bool = False) -> int:
    """List every planned action; reject incomplete/ambiguous state before any writes."""
    base = base_url.rstrip("/") + "/v1/feeds"
    headers = {"X-Auth-Token": token}
    response = client.get(base, headers=headers)
    response.raise_for_status()
    by_url: dict[str, list[int]] = {}
    for feed in response.json():
        by_url.setdefault(feed["feed_url"], []).append(feed["id"])

    invalid: set[str] = set()
    for repair in REPAIRS:
        ids = by_url.get(repair.old, [])
        if len(ids) != 1 or (repair.new is not None and repair.new in by_url):
            invalid.add(repair.old)

    counts = {"repoint": 0, "delete": 0, "skip": 0, "failed": 0}
    for repair in REPAIRS:
        target = f" -> {repair.new}" if repair.new else ""
        if repair.old in invalid or (apply and invalid):
            ids = by_url.get(repair.old, [])
            if repair.old not in invalid:
                reason = "plan incomplete; no mutations"
            else:
                reason = (
                    "missing from Miniflux"
                    if not ids
                    else "ambiguous URL or replacement already subscribed"
                )
            print(f"skip {repair.old}{target} | {reason}; {repair.reason}")
            counts["skip"] += 1
            continue
        if apply:
            url = f"{base}/{by_url[repair.old][0]}"
            try:
                if repair.action == "repoint":
                    result = client.put(url, headers=headers, json={"feed_url": repair.new})
                else:
                    result = client.delete(url, headers=headers)
                result.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"skip {repair.old}{target} | API failure: {exc}; {repair.reason}")
                counts["failed"] += 1
                continue
        print(f"{repair.action} {repair.old}{target} | {repair.reason}")
        counts[repair.action] += 1
    mode = "apply" if apply else "dry-run"
    print(
        f"Summary ({mode}): repoint={counts['repoint']} delete={counts['delete']} "
        f"skip={counts['skip']} failed={counts['failed']}"
    )
    return 1 if counts["skip"] or counts["failed"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="List actions without changing Miniflux (default)"
    )
    mode.add_argument(
        "--apply", action="store_true", help="Apply the listed actions after approval"
    )
    args = parser.parse_args()
    base = os.environ.get("MINIFLUX_URL")
    token = os.environ.get("MINIFLUX_TOKEN")
    if not base or not token:
        parser.error("MINIFLUX_URL and MINIFLUX_TOKEN must be set")
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            result = run(client, base, token, apply=args.apply)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        print(f"Miniflux maintenance failed: {exc}", file=sys.stderr)
        sys.exit(1)
    sys.exit(result)


if __name__ == "__main__":
    main()
