"""Check all feeds in feeds.xml for HTTP health status."""

import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

FEEDS_XML = Path(__file__).resolve().parent.parent / "feeds.xml"
TIMEOUT = 10
MAX_WORKERS = 20
USER_AGENT = "Mozilla/5.0 RSS Feed Checker"


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
    try:
        r = requests.head(
            url,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        return url, r.status_code
    except requests.exceptions.SSLError:
        return url, "ssl_error"
    except requests.exceptions.Timeout:
        return url, "timeout"
    except requests.exceptions.ConnectionError:
        return url, "conn_error"
    except Exception as e:
        return url, str(e)[:50]


def main():
    if not FEEDS_XML.exists():
        print(f"Error: {FEEDS_XML} not found", file=sys.stderr)
        sys.exit(1)

    feeds = parse_feeds(FEEDS_XML)
    unique_urls = {}
    for f in feeds:
        url = f["xmlUrl"]
        if url not in unique_urls:
            unique_urls[url] = []
        unique_urls[url].append(f)

    print(f"Feeds: {len(feeds)} entries, {len(unique_urls)} unique URLs\n")
    print("Checking feed URLs ...\n")

    results = {"ok": [], "error": []}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(check_url, url): url for url in unique_urls}
        done = 0
        for future in as_completed(futures):
            done += 1
            url, status = future.result()
            if status == "skip":
                continue
            entry = {"url": url, "status": status, "feeds": unique_urls[url]}
            if isinstance(status, int) and 200 <= status < 400:
                results["ok"].append(entry)
            else:
                results["error"].append(entry)
            if done % 50 == 0:
                print(f"  Progress: {done}/{len(futures)}")

    ok, err = len(results["ok"]), len(results["error"])
    print(f"\nResults: {ok} OK, {err} broken/unreachable\n")

    if results["error"]:
        results["error"].sort(key=lambda e: str(e["status"]))
        print("=" * 80)
        print("BROKEN / UNREACHABLE FEEDS")
        print("=" * 80)
        for e in results["error"]:
            names = ", ".join(f["name"] for f in e["feeds"])
            folders = ", ".join(f["folder"] for f in e["feeds"])
            print(f"  [{e['status']:>12}]  {e['url']}")
            print(f"                 Feed(s): {names}")
            print(f"                 Folder(s): {folders}")
            print()


if __name__ == "__main__":
    main()
