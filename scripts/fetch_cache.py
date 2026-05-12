"""Fetch and cache recent articles from all feeds in feeds.xml.

Cache lives at .cache/feeds.json. Each entry stores up to MAX_ITEMS articles
per feed with title, link, published date, and a short summary. Feeds are
only re-fetched when their cache entry is older than --max-age hours.
"""

import argparse
import asyncio
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import httpx

FEEDS_XML = Path(__file__).resolve().parent.parent / "feeds.xml"
CACHE_FILE = Path(__file__).resolve().parent.parent / ".cache" / "feeds.json"
TIMEOUT = 12
MAX_WORKERS = 20
MAX_ITEMS = 10
USER_AGENT = "Mozilla/5.0 Security News Aggregator"


def load_feeds(path: Path) -> list[dict]:
    tree = ET.parse(path)
    feeds = []
    for folder in tree.getroot().find("body"):
        folder_name = folder.get("text", "")
        for feed in folder:
            url = feed.get("xmlUrl", "")
            if url:
                feeds.append({"name": feed.get("text", ""), "url": url, "folder": folder_name})
    return feeds


def load_cache(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"generated_at": None, "feeds": {}}


def is_fresh(entry: dict, max_age_hours: float) -> bool:
    ts = entry.get("fetched_at")
    if not ts:
        return False
    try:
        fetched = datetime.fromisoformat(ts)
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
        return age_h < max_age_hours
    except Exception:
        return False


def _strip(s: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").strip()


def parse_items(content: str, max_items: int) -> list[dict]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    items: list[dict] = []

    for item in root.findall(".//item")[:max_items]:
        title = _strip(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        summary = _strip(item.findtext("description"))[:500]
        if title:
            items.append({"title": title, "link": link, "published": pub, "summary": summary})

    if not items:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns)[:max_items]:
            title = _strip(entry.findtext("a:title", namespaces=ns))
            link_el = entry.find("a:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            pub = (
                entry.findtext("a:published", namespaces=ns)
                or entry.findtext("a:updated", namespaces=ns)
                or ""
            ).strip()
            summary = _strip(
                entry.findtext("a:summary", namespaces=ns)
                or entry.findtext("a:content", namespaces=ns)
            )[:500]
            if title:
                items.append({"title": title, "link": link, "published": pub, "summary": summary})

    return items


async def fetch_one(
    client: httpx.AsyncClient, feed: dict, sem: asyncio.Semaphore
) -> tuple[str, dict]:
    url = feed["url"]
    now = datetime.now(timezone.utc).isoformat()
    async with sem:
        try:
            r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
            r.raise_for_status()
            items = parse_items(r.text, MAX_ITEMS)
            return url, {
                "name": feed["name"],
                "folder": feed["folder"],
                "fetched_at": now,
                "items": items,
                "error": None,
            }
        except Exception as e:
            return url, {
                "name": feed["name"],
                "folder": feed["folder"],
                "fetched_at": now,
                "items": [],
                "error": str(e)[:120],
            }


async def refresh(
    feeds: list[dict],
    cache: dict,
    max_age: float,
    folder_filter: list[str],
    url_filter: list[str],
) -> dict:
    to_fetch = []
    for feed in feeds:
        if folder_filter and feed["folder"] not in folder_filter:
            continue
        if url_filter and feed["url"] not in url_filter:
            continue
        existing = cache["feeds"].get(feed["url"], {})
        if not is_fresh(existing, max_age):
            to_fetch.append(feed)

    skipped = len(feeds) - len(to_fetch)
    if folder_filter or url_filter:
        skipped = 0
    print(f"Fetching {len(to_fetch)} feeds ({skipped} fresh, skipped)…", file=sys.stderr)

    sem = asyncio.Semaphore(MAX_WORKERS)
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        results = await asyncio.gather(*[fetch_one(client, f, sem) for f in to_fetch])

    errors = 0
    for url, data in results:
        cache["feeds"][url] = data
        if data["error"]:
            errors += 1

    cache["generated_at"] = datetime.now(timezone.utc).isoformat()
    if errors:
        print(f"  {errors} fetch errors (see cache for details)", file=sys.stderr)
    return cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/update article cache from feeds.xml")
    parser.add_argument("--max-age", type=float, default=6.0,
                        help="Re-fetch feeds older than N hours (default 6)")
    parser.add_argument("--folders", nargs="*", metavar="FOLDER",
                        help="Limit to these folder names")
    parser.add_argument("--urls", nargs="*", metavar="URL",
                        help="Limit to these feed URLs")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch everything regardless of age")
    parser.add_argument("--stats", action="store_true",
                        help="Print cache stats and exit")
    args = parser.parse_args()

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache = load_cache(CACHE_FILE)

    if args.stats:
        total = len(cache["feeds"])
        with_items = sum(1 for v in cache["feeds"].values() if v.get("items"))
        errors = sum(1 for v in cache["feeds"].values() if v.get("error"))
        stale = sum(1 for v in cache["feeds"].values() if not is_fresh(v, 6))
        print(f"generated : {cache.get('generated_at', 'never')}")
        print(f"feeds     : {total} total / {with_items} with articles / {errors} errors / {stale} stale")
        return

    max_age = 0.0 if args.force else args.max_age
    feeds = load_feeds(FEEDS_XML)
    cache = asyncio.run(refresh(feeds, cache, max_age, args.folders or [], args.urls or []))
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    total_items = sum(len(v.get("items", [])) for v in cache["feeds"].values())
    print(f"Cached {len(cache['feeds'])} feeds, {total_items} articles → {CACHE_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
