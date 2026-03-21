"""Show statistics about feeds.xml."""

import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

FEEDS_XML = Path(__file__).resolve().parent.parent / "feeds.xml"


def main():
    if not FEEDS_XML.exists():
        print(f"Error: {FEEDS_XML} not found", file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(FEEDS_XML)
    body = tree.getroot().find("body")

    folders = []
    feeds = []
    xml_urls = set()
    domains = Counter()

    for folder in body:
        if folder.get("type") == "rss":
            continue
        folder_name = folder.get("text", "(unnamed)")
        folder_count = 0
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
                xml_urls.add(feed.get("xmlUrl", ""))
                try:
                    domain = urlparse(feed.get("htmlUrl", "")).netloc.lower()
                    domain = domain.removeprefix("www.")
                    if domain:
                        domains[domain] += 1
                except Exception:
                    pass
                folder_count += 1
        folders.append((folder_name, folder_count))

    print("=" * 60)
    print("FEEDS.XML STATISTICS")
    print("=" * 60)
    print(f"  Total feed entries:    {len(feeds)}")
    print(f"  Unique feed URLs:      {len(xml_urls)}")
    print(f"  Unique site domains:   {len(domains)}")
    print(f"  Folders:               {len(folders)}")
    print()

    # Duplicates
    url_counts = Counter(f["xmlUrl"] for f in feeds)
    dupes = {url: count for url, count in url_counts.items() if count > 1}
    if dupes:
        print(f"  Duplicate URLs:        {len(dupes)}")
        for url, count in sorted(dupes.items(), key=lambda x: -x[1]):
            names = [f["name"] for f in feeds if f["xmlUrl"] == url]
            print(f"    {count}x  {names[0]} ({url})")
    print()

    print("FOLDERS:")
    for name, count in sorted(folders, key=lambda x: -x[1]):
        bar = "#" * count
        print(f"  {count:3d}  {name:45s} {bar}")
    print()

    # Protocol breakdown
    http = sum(1 for u in xml_urls if u.startswith("http://"))
    https = sum(1 for u in xml_urls if u.startswith("https://"))
    other = len(xml_urls) - http - https
    print(f"  HTTPS feeds: {https}  |  HTTP feeds: {http}  |  Other: {other}")


if __name__ == "__main__":
    main()
