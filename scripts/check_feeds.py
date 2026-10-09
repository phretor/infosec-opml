"""Check all feeds in feeds.xml for HTTP health status, optionally removing dead ones."""

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

FEEDS_XML = Path(__file__).resolve().parent.parent / "feeds.xml"
TIMEOUT = 10
MAX_WORKERS = 20
USER_AGENT = "Mozilla/5.0 RSS Feed Checker"
RETRY_PAUSE_SECONDS = 5


def parse_feeds(path: Path) -> list[dict]:
    tree = ET.parse(path)
    feeds = []
    for folder in tree.getroot().find("body"):
        folder_name = folder.get("text", "")
        for feed in folder:
            if feed.get("type") == "rss":
                feeds.append(
                    {
                        "name": feed.get("text", ""),
                        "xmlUrl": feed.get("xmlUrl", ""),
                        "htmlUrl": feed.get("htmlUrl", ""),
                        "folder": folder_name,
                    }
                )
    return feeds


def check_url(url: str) -> tuple[str, int | str]:
    if not url.startswith(("http://", "https://")):
        return url, "skip"
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.head(url, timeout=TIMEOUT, headers=headers, allow_redirects=True)
        if r.status_code in (403, 405):
            # Some servers reject HEAD; retry with streaming GET to avoid downloading body
            r = requests.get(url, timeout=TIMEOUT, headers=headers, allow_redirects=True, stream=True)
            r.close()
        return url, r.status_code
    except requests.exceptions.SSLError:
        return url, "ssl_error"
    except requests.exceptions.Timeout:
        return url, "timeout"
    except requests.exceptions.ConnectionError:
        return url, "conn_error"
    except Exception as e:
        return url, str(e)[:50]


def classify(status: int | str) -> str:
    """Return 'ok', 'dead', or 'transient'."""
    if isinstance(status, int):
        if 200 <= status < 400:
            return "ok"
        if status == 429 or status >= 500:
            return "transient"
        return "dead"  # 4xx: resource gone or permanently inaccessible
    return "transient" if status == "timeout" else "dead"


def remove_feeds(path: Path, dead_urls: set[str]) -> tuple[int, int]:
    """Remove feed outlines from the OPML file. Returns (feeds_removed, folders_removed)."""
    tree = ET.parse(path)
    root = tree.getroot()
    body = root.find("body")

    feeds_removed = 0
    folders_removed = 0

    for folder in list(body):
        for feed in list(folder):
            if feed.get("xmlUrl") in dead_urls:
                folder.remove(feed)
                feeds_removed += 1
        if len(folder) == 0:
            body.remove(folder)
            folders_removed += 1

    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode")
    path.write_text(f"<?xml version='1.0' encoding='UTF-8'?>\n{xml_str}\n", encoding="utf-8")

    return feeds_removed, folders_removed


def print_section(title: str, entries: list[dict]) -> None:
    if not entries:
        return
    entries.sort(key=lambda e: str(e["status"]))
    print("=" * 80)
    print(title)
    print("=" * 80)
    for e in entries:
        names = ", ".join(f["name"] for f in e["feeds"])
        folders = ", ".join(f["folder"] for f in e["feeds"])
        print(f"  [{e['status']:>12}]  {e['url']}")
        print(f"                 Feed(s): {names}")
        print(f"                 Folder(s): {folders}")
        print()


def check_urls(urls: list[str], max_workers: int = MAX_WORKERS) -> dict[str, int | str]:
    """Concurrently check a list of URLs. Returns {url: status}."""
    results: dict[str, int | str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(check_url, url): url for url in urls}
        for future in as_completed(futures):
            url, status = future.result()
            if status != "skip":
                results[url] = status
    return results


def classify_batch(
    urls: list[str], max_workers: int = MAX_WORKERS, pause_seconds: float = RETRY_PAUSE_SECONDS
) -> dict[str, tuple[str, int | str]]:
    """Classify URLs as ok/dead/transient with a one-shot retry on initially-dead ones.

    Returns {url: (bucket, status)}. Dead URLs are retried once after a short
    pause; successful retries are promoted out of the dead set.
    """
    initial = check_urls(urls, max_workers=max_workers)
    classified: dict[str, tuple[str, int | str]] = {
        url: (classify(status), status) for url, status in initial.items()
    }

    dead_urls = [url for url, (bucket, _) in classified.items() if bucket == "dead"]
    if dead_urls:
        time.sleep(pause_seconds)
        retry = check_urls(dead_urls, max_workers=max_workers)
        for url, status in retry.items():
            new_bucket = classify(status)
            if new_bucket != "dead":
                classified[url] = (new_bucket, status)
    return classified


def main() -> None:
    parser = argparse.ArgumentParser(description="Check RSS/Atom feed health in feeds.xml")
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove dead feeds (4xx, conn_error, ssl_error) from feeds.xml",
    )
    parser.add_argument(
        "--remove-all",
        action="store_true",
        help="Remove all erroring feeds including transient failures (timeouts, 5xx, 429)",
    )
    parser.add_argument(
        "--fail-on-dead",
        action="store_true",
        help="Exit non-zero if any feed is classified dead after the retry pass",
    )
    parser.add_argument(
        "--retry-pause-seconds",
        type=float,
        default=RETRY_PAUSE_SECONDS,
        help="Seconds to pause before retrying initially-dead URLs",
    )
    args = parser.parse_args()

    if not FEEDS_XML.exists():
        print(f"Error: {FEEDS_XML} not found", file=sys.stderr)
        sys.exit(1)

    feeds = parse_feeds(FEEDS_XML)
    unique_urls: dict[str, list[dict]] = {}
    for f in feeds:
        url = f["xmlUrl"]
        if url not in unique_urls:
            unique_urls[url] = []
        unique_urls[url].append(f)

    print(f"Feeds: {len(feeds)} entries, {len(unique_urls)} unique URLs\n")
    print("Checking feed URLs ...\n")

    classified = classify_batch(list(unique_urls), pause_seconds=args.retry_pause_seconds)
    results: dict[str, list[dict]] = {"ok": [], "dead": [], "transient": []}
    for url, (bucket, status) in classified.items():
        results[bucket].append({"url": url, "status": status, "feeds": unique_urls[url]})

    ok, dead, transient = len(results["ok"]), len(results["dead"]), len(results["transient"])
    print(f"\nResults: {ok} OK, {dead} dead, {transient} transient\n")

    print_section("DEAD FEEDS (4xx errors, connection failures)", results["dead"])
    print_section("TRANSIENT ERRORS (timeouts, 5xx, rate-limited)", results["transient"])

    if args.remove or args.remove_all:
        to_remove = {e["url"] for e in results["dead"]}
        if args.remove_all:
            to_remove |= {e["url"] for e in results["transient"]}
        if to_remove:
            feeds_removed, folders_removed = remove_feeds(FEEDS_XML, to_remove)
            label = "dead + transient" if args.remove_all else "dead"
            print(f"Removed {feeds_removed} {label} feed(s), {folders_removed} empty folder(s)")
        else:
            print("Nothing to remove.")

    if args.fail_on_dead and dead > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
