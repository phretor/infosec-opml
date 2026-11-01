"""Push feeds added to feeds.xml by a merge into Miniflux (additive only).

This is the repo -> Miniflux half of the sync; `miniflux_sync` is the Miniflux -> repo half.

What gets pushed is the merged diff, not "in the repo but not in Miniflux": only `xmlUrl`s that
appear in the post-merge `feeds.xml` and not in the pre-merge one. A feed the maintainer deleted
in Miniflux whose removal has not been pulled into the repo yet is therefore never re-added.

The only Miniflux calls made are `GET /v1/categories`, `GET /v1/feeds`, and `POST /v1/feeds`.
Existing feeds and categories are never modified, renamed, or deleted, and no category is ever
created: an addition whose folder has no matching Miniflux category fails instead. Re-running is
safe: additions already present in Miniflux are skipped, and Miniflux itself refuses duplicates.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

import httpx

from scripts.miniflux_sync import FEEDS_XML, Feed, parse_opml

# Miniflux fetches and parses the feed synchronously while creating it.
HTTP_TIMEOUT = 60.0
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal")

Outcome = Literal["created", "would-create", "present", "failed"]


@dataclass(frozen=True)
class PushResult:
    """What happened to one added feed."""

    feed: Feed
    outcome: Outcome
    detail: str = ""


class MinifluxError(Exception):
    """Miniflux answered a request with a non-2xx status."""


def plan_additions(before: list[Feed], after: list[Feed]) -> list[Feed]:
    """Return feeds whose `xmlUrl` is in `after` but not in `before`, in `after` order."""
    known = {f.xml_url for f in before}
    additions: list[Feed] = []
    for f in after:
        if f.xml_url not in known:
            known.add(f.xml_url)
            additions.append(f)
    return additions


def url_problem(url: str) -> str | None:
    """Return why Miniflux must not be asked to fetch `url`, or None when it is acceptable.

    Miniflux fetches the URL server-side when the feed is created, so only public http(s)
    DNS names are accepted.
    """
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        return f"scheme must be http or https, got {parts.scheme!r}"
    host = (parts.hostname or "").lower()
    if not host:
        return "URL has no host"
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return f"IP-literal host {host!r} is not accepted"
    if host == "localhost" or host.endswith(_BLOCKED_HOST_SUFFIXES) or "." not in host:
        return f"host {host!r} is not a public DNS name"
    return None


def url_key(url: str) -> str:
    """Comparison key that treats scheme, host case, and a trailing slash as insignificant."""
    parts = urlsplit(url.strip())
    return urlunsplit(("", parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


class MinifluxApi:
    """The complete set of Miniflux operations the push direction is allowed to perform."""

    def __init__(self, client: httpx.Client, base_url: str, api_token: str) -> None:
        self._client = client
        self._base = base_url.rstrip("/")
        self._headers = {"X-Auth-Token": api_token}

    def _request(self, method: str, path: str, json: object | None = None) -> httpx.Response:
        resp = self._client.request(method, self._base + path, headers=self._headers, json=json)
        if resp.is_success:
            return resp
        try:
            message = str(resp.json().get("error_message", ""))
        except ValueError:
            message = ""
        raise MinifluxError(f"{method} {path} -> HTTP {resp.status_code}: {message or resp.text}")

    def category_ids(self) -> dict[str, int]:
        """GET /v1/categories as {title: id}."""
        return {c["title"]: int(c["id"]) for c in self._request("GET", "/v1/categories").json()}

    def feed_urls(self) -> list[str]:
        """GET /v1/feeds as the list of subscribed feed URLs."""
        return [f["feed_url"] for f in self._request("GET", "/v1/feeds").json()]

    def create_feed(self, feed_url: str, category_id: int) -> int:
        """POST /v1/feeds; returns the new feed id."""
        body = {"feed_url": feed_url, "category_id": category_id}
        return int(self._request("POST", "/v1/feeds", json=body).json()["feed_id"])


def push_additions(
    api: MinifluxApi, additions: list[Feed], *, dry_run: bool = False
) -> list[PushResult]:
    """Subscribe Miniflux to each addition it does not already have.

    Each addition is independent: a failure is recorded and the remaining ones are still
    attempted. Miniflux is only contacted when at least one addition has an acceptable URL.
    """
    problems = {f.xml_url: url_problem(f.xml_url) for f in additions}
    categories: dict[str, int] = {}
    present: set[str] = set()
    if any(p is None for p in problems.values()):
        categories = api.category_ids()
        present = {url_key(u) for u in api.feed_urls()}

    results: list[PushResult] = []
    for f in additions:
        problem = problems[f.xml_url]
        if problem is not None:
            results.append(PushResult(f, "failed", problem))
            continue
        key = url_key(f.xml_url)
        if key in present:
            results.append(PushResult(f, "present", "already subscribed in Miniflux"))
            continue
        category_id = categories.get(f.folder)
        if category_id is None:
            detail = f"no Miniflux category titled {f.folder!r}; create it in Miniflux first"
            results.append(PushResult(f, "failed", detail))
            continue
        if dry_run:
            results.append(PushResult(f, "would-create", f"category_id={category_id}"))
            continue
        try:
            feed_id = api.create_feed(f.xml_url, category_id)
        except MinifluxError as exc:
            results.append(PushResult(f, "failed", str(exc)))
            continue
        present.add(key)
        results.append(PushResult(f, "created", f"feed_id={feed_id}"))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Subscribe Miniflux to feeds added to feeds.xml (additive only)"
    )
    parser.add_argument(
        "--before", required=True, type=Path, help="feeds.xml as it was before the merge"
    )
    parser.add_argument(
        "--after", default=FEEDS_XML, type=Path, help="feeds.xml after the merge (default: repo)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Read Miniflux and print the plan; create nothing"
    )
    args = parser.parse_args(argv)

    before = parse_opml(args.before.read_text(encoding="utf-8"))
    after = parse_opml(args.after.read_text(encoding="utf-8"))
    additions = plan_additions(before, after)
    if not additions:
        print("No feed additions to push.")
        return 0

    base = os.environ.get("MINIFLUX_URL")
    token = os.environ.get("MINIFLUX_TOKEN")
    if not base or not token:
        print("error: MINIFLUX_URL and MINIFLUX_TOKEN must be set", file=sys.stderr)
        return 2

    # No redirects: a redirected POST can silently turn into a GET.
    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=False) as client:
        results = push_additions(MinifluxApi(client, base, token), additions, dry_run=args.dry_run)

    for r in results:
        print(f"[{r.outcome:>12}] {r.feed.name} ({r.feed.folder}) {r.feed.xml_url} {r.detail}")
    failed = sum(r.outcome == "failed" for r in results)
    print(f"{len(results)} addition(s): {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
