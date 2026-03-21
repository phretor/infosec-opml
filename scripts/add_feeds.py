"""Add feeds to feeds.xml from command line or OPML file."""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

FEEDS_XML = Path(__file__).resolve().parent.parent / "feeds.xml"
TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 RSS Feed Checker"


def get_existing_urls(tree: ET.ElementTree) -> set[str]:
    urls = set()
    for outline in tree.getroot().iter("outline"):
        url = outline.get("xmlUrl", "")
        if url:
            urls.add(url.lower().rstrip("/"))
    return urls


def get_folder_names(tree: ET.ElementTree) -> list[str]:
    names = []
    for folder in tree.getroot().find("body"):
        if folder.get("type") != "rss":
            names.append(folder.get("text", ""))
    return names


def find_folder(body: ET.Element, folder_name: str) -> ET.Element | None:
    for folder in body:
        if folder.get("text") == folder_name:
            return folder
    return None


def check_url(url: str) -> int | str:
    try:
        r = requests.head(
            url,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        return r.status_code
    except Exception as e:
        return str(e)[:60]


def add_feed(
    tree: ET.ElementTree,
    name: str,
    xml_url: str,
    html_url: str,
    folder_name: str,
    *,
    verify: bool = True,
) -> bool:
    existing = get_existing_urls(tree)
    if xml_url.lower().rstrip("/") in existing:
        print(f"  SKIP (duplicate): {name}")
        return False

    if verify:
        status = check_url(xml_url)
        if isinstance(status, int) and status >= 400:
            print(f"  SKIP (HTTP {status}): {name} -- {xml_url}")
            return False
        elif not isinstance(status, int):
            print(f"  SKIP ({status}): {name} -- {xml_url}")
            return False

    body = tree.getroot().find("body")
    folder = find_folder(body, folder_name)
    if folder is None:
        folder = ET.SubElement(body, "outline")
        folder.set("text", folder_name)
        folder.set("title", folder_name)
        print(f"  Created new folder: {folder_name}")

    feed = ET.SubElement(folder, "outline")
    feed.set("text", name)
    feed.set("title", name)
    feed.set("type", "rss")
    feed.set("xmlUrl", xml_url)
    feed.set("htmlUrl", html_url)
    print(f"  ADDED: {name} -> {folder_name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Add feeds to feeds.xml")
    parser.add_argument(
        "--name", help="Feed name (for single feed mode)"
    )
    parser.add_argument(
        "--xml-url", help="Feed RSS/Atom URL (for single feed mode)"
    )
    parser.add_argument(
        "--html-url", help="Site URL (for single feed mode)", default=""
    )
    parser.add_argument(
        "--folder", help="Target folder name (for single feed mode)"
    )
    parser.add_argument(
        "--from-opml", help="Import from OPML file", type=Path
    )
    parser.add_argument(
        "--target-folder",
        help="Target folder for all OPML imports",
        default="🌐 Infosec | Blogs",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip HTTP verification",
    )
    parser.add_argument(
        "--list-folders",
        action="store_true",
        help="List available folders and exit",
    )
    args = parser.parse_args()

    tree = ET.parse(FEEDS_XML)

    if args.list_folders:
        for name in get_folder_names(tree):
            print(f"  {name}")
        return

    added = 0
    if args.name and args.xml_url and args.folder:
        if add_feed(
            tree,
            args.name,
            args.xml_url,
            args.html_url,
            args.folder,
            verify=not args.no_verify,
        ):
            added += 1
    elif args.from_opml:
        if not args.from_opml.exists():
            print(f"Error: {args.from_opml} not found", file=sys.stderr)
            sys.exit(1)
        src = ET.parse(args.from_opml)
        for outline in src.getroot().iter("outline"):
            if outline.get("type") == "rss":
                if add_feed(
                    tree,
                    outline.get("text", ""),
                    outline.get("xmlUrl", ""),
                    outline.get("htmlUrl", ""),
                    args.target_folder,
                    verify=not args.no_verify,
                ):
                    added += 1
    else:
        parser.print_help()
        sys.exit(1)

    if added > 0:
        ET.indent(tree, space="  ")
        tree.write(FEEDS_XML, encoding="UTF-8", xml_declaration=True)
        print(f"\nAdded {added} feeds. Written to {FEEDS_XML}")
    else:
        print("\nNo feeds added.")


if __name__ == "__main__":
    main()
