"""Sync Miniflux-exported OPML into the repo's feeds.xml, README, and CHANGELOG.

The pure pipeline (`sync_pipeline`) performs no I/O: given the raw Miniflux OPML
text and the current state of `feeds.xml`, README, and CHANGELOG, it returns
either `NoChange` or a `SyncOutput` carrying patched content. All I/O lives in
`main`.

The OPML normalizer here is the sole acceptable path for anything that writes
`feeds.xml`.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import date as date_type
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
FEEDS_XML = REPO_ROOT / "feeds.xml"
README = REPO_ROOT / "README.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

FEED_ATTR_ORDER = ("text", "title", "type", "xmlUrl", "htmlUrl")
FOLDER_ATTR_ORDER = ("text", "title")
OPML_TITLE = "Information and Cyber Security RSS/Atom Feeds"


@dataclass(frozen=True)
class Feed:
    """A single feed subscription."""

    name: str
    folder: str
    xml_url: str
    html_url: str
    type_: str = "rss"
    title: str = ""


@dataclass(frozen=True)
class SyncOutput:
    """A real diff result: patched content plus the change sets."""

    new_feeds_xml: str
    new_readme: str
    new_changelog: str
    added: tuple[Feed, ...]
    removed: tuple[Feed, ...]
    feed_count: int
    folder_count: int


@dataclass(frozen=True)
class NoChange:
    """Normalized Miniflux output is byte-identical to current feeds.xml."""

    reason: str = "no_change"


SyncResult = SyncOutput | NoChange


def parse_opml(opml_text: str) -> list[Feed]:
    """Parse OPML text into an ordered list of Feed records.

    Folders are preserved in the order they appear. Empty folders are dropped
    because Miniflux omits them already and the repo's convention mirrors that.
    """
    root = ET.fromstring(opml_text)
    body = root.find("body")
    if body is None:
        return []
    feeds: list[Feed] = []
    for folder in body:
        if folder.tag != "outline":
            continue
        folder_name = folder.get("text") or folder.get("title") or ""
        for feed in folder:
            if feed.tag != "outline" or feed.get("xmlUrl") is None:
                continue
            feeds.append(
                Feed(
                    name=feed.get("text") or feed.get("title") or "",
                    folder=folder_name,
                    xml_url=feed.get("xmlUrl", ""),
                    html_url=feed.get("htmlUrl", ""),
                    type_=feed.get("type", "rss"),
                    title=feed.get("title") or feed.get("text") or "",
                )
            )
    return feeds


def _attr_fragment(outline: ET.Element, order: tuple[str, ...]) -> str:
    parts: list[str] = []
    for key in order:
        val = outline.get(key)
        if val is None:
            continue
        parts.append(f"{key}={quoteattr(val)}")
    return " ".join(parts)


def normalize_opml(opml_text: str) -> str:
    """Produce a stable 2-space-indented OPML 1.0 string from any OPML input.

    Attribute emission order is fixed: `text, title, type, xmlUrl, htmlUrl` on
    feed outlines; `text, title` on folders. Empty folders are omitted so the
    output matches the repo convention (Miniflux already omits them).
    """
    root = ET.fromstring(opml_text)
    body = root.find("body")

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="1.0">',
        "  <head>",
        f"    <title>{escape(OPML_TITLE)}</title>",
        "  </head>",
        "  <body>",
    ]

    if body is not None:
        for folder in body:
            if folder.tag != "outline":
                continue
            feed_children = [
                child
                for child in folder
                if child.tag == "outline" and child.get("xmlUrl") is not None
            ]
            if not feed_children:
                continue
            folder_attrs = _attr_fragment(folder, FOLDER_ATTR_ORDER)
            lines.append(f"    <outline {folder_attrs}>")
            for feed in feed_children:
                feed_attrs = _attr_fragment(feed, FEED_ATTR_ORDER)
                lines.append(f"      <outline {feed_attrs}></outline>")
            lines.append("    </outline>")

    lines.append("  </body>")
    lines.append("</opml>")
    lines.append("")
    return "\n".join(lines)


def diff_feeds(
    current: list[Feed], incoming: list[Feed]
) -> tuple[tuple[Feed, ...], tuple[Feed, ...]]:
    """Return (added, removed) feeds compared by xmlUrl set equality.

    A feed whose xmlUrl changed but whose name stayed the same surfaces as a
    pair: one Removed (old URL) and one Added (new URL). This is deliberate —
    Miniflux has no stable identity across URL changes.
    """
    by_url_current = {f.xml_url: f for f in current}
    by_url_incoming = {f.xml_url: f for f in incoming}
    added = tuple(by_url_incoming[u] for u in by_url_incoming if u not in by_url_current)
    removed = tuple(by_url_current[u] for u in by_url_current if u not in by_url_incoming)
    return added, removed


def patch_readme(readme_text: str, feed_count: int, folder_count: int) -> str:
    """Rewrite the feed-count and folder-count sentences in the README.

    Raises ValueError when either anchor sentence is missing, so a drifted
    README surfaces as a workflow failure rather than silently shipping stale
    counts.
    """
    out, feed_hits = re.subn(
        r"collection of \d+ information security",
        f"collection of {feed_count} information security",
        readme_text,
        count=1,
    )
    out, folder_hits = re.subn(
        r"organized into \d+ permanent, flat folders",
        f"organized into {folder_count} permanent, flat folders",
        out,
        count=1,
    )
    if feed_hits == 0 or folder_hits == 0:
        missing = []
        if feed_hits == 0:
            missing.append("feed-count")
        if folder_hits == 0:
            missing.append("folder-count")
        raise ValueError(
            f"README anchor sentence(s) not found: {', '.join(missing)}. "
            "Restore the sentence or update patch_readme."
        )
    return out


def _format_feed_bullet(f: Feed) -> str:
    return f"- {f.name} ({f.folder})"


def build_changelog_entry(
    sync_date: date_type,
    added: tuple[Feed, ...],
    removed: tuple[Feed, ...],
    feed_count: int,
    folder_count: int,
) -> str:
    """Build a mechanical, chronological CHANGELOG entry."""
    lines = [f"## {sync_date.isoformat()}", ""]
    if added:
        lines.append("### Added")
        for f in sorted(added, key=lambda x: (x.folder, x.name)):
            lines.append(_format_feed_bullet(f))
        lines.append("")
    if removed:
        lines.append("### Removed")
        for f in sorted(removed, key=lambda x: (x.folder, x.name)):
            lines.append(_format_feed_bullet(f))
        lines.append("")
    lines.append("### Net result")
    lines.append(f"- {feed_count} feeds across {folder_count} nonempty flat folders")
    lines.append("")
    return "\n".join(lines)


def prepend_changelog(changelog_text: str, entry: str) -> str:
    """Insert a new entry just under the top-level '# Changelog' header."""
    header_match = re.match(r"(#\s+Changelog\s*\n+)", changelog_text)
    if not header_match:
        return f"# Changelog\n\n{entry}\n{changelog_text}"
    header = header_match.group(1)
    rest = changelog_text[header_match.end() :]
    return f"{header}{entry}\n{rest}"


def sync_pipeline(
    miniflux_opml: str,
    current_feeds_xml: str,
    current_readme: str,
    current_changelog: str,
    sync_date: date_type,
) -> SyncResult:
    """Pure sync function. No I/O.

    Returns `NoChange` when the normalized Miniflux output is byte-identical to
    the current `feeds.xml`; otherwise returns a `SyncOutput` with the patched
    files and change sets.
    """
    normalized = normalize_opml(miniflux_opml)
    if normalized == current_feeds_xml:
        return NoChange()

    current_feeds = parse_opml(current_feeds_xml) if current_feeds_xml.strip() else []
    incoming_feeds = parse_opml(miniflux_opml)
    added, removed = diff_feeds(current_feeds, incoming_feeds)

    feed_count = len(incoming_feeds)
    folder_count = len({f.folder for f in incoming_feeds})

    new_readme = patch_readme(current_readme, feed_count, folder_count)

    if added or removed:
        entry = build_changelog_entry(sync_date, added, removed, feed_count, folder_count)
        new_changelog = prepend_changelog(current_changelog, entry)
    else:
        new_changelog = current_changelog

    return SyncOutput(
        new_feeds_xml=normalized,
        new_readme=new_readme,
        new_changelog=new_changelog,
        added=added,
        removed=removed,
        feed_count=feed_count,
        folder_count=folder_count,
    )


def fetch_miniflux_opml(base_url: str, api_token: str) -> str:
    """Fetch the OPML export from Miniflux.

    Raises on any non-2xx response so an unreachable Miniflux surfaces as a
    workflow failure rather than a silent empty PR.
    """
    url = base_url.rstrip("/") + "/v1/export"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(url, headers={"X-Auth-Token": api_token})
        resp.raise_for_status()
        return resp.text


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Miniflux OPML into the repo")
    parser.add_argument(
        "--input",
        help="Read OPML from file instead of fetching Miniflux (for local testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned action; do not write files",
    )
    args = parser.parse_args()

    if args.input:
        opml_text = Path(args.input).read_text(encoding="utf-8")
    else:
        base = os.environ.get("MINIFLUX_URL")
        token = os.environ.get("MINIFLUX_TOKEN")
        if not base or not token:
            print(
                "error: MINIFLUX_URL and MINIFLUX_TOKEN must be set (or pass --input)",
                file=sys.stderr,
            )
            return 2
        opml_text = fetch_miniflux_opml(base, token)

    sync_date = datetime.now(tz=UTC).date()

    current_feeds_xml = FEEDS_XML.read_text(encoding="utf-8") if FEEDS_XML.exists() else ""
    current_readme = README.read_text(encoding="utf-8") if README.exists() else ""
    current_changelog = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else "# Changelog\n\n"

    result = sync_pipeline(opml_text, current_feeds_xml, current_readme, current_changelog, sync_date)

    if isinstance(result, NoChange):
        print("No change: normalized Miniflux output matches feeds.xml.")
        return 0

    print(
        f"Change detected: +{len(result.added)} / -{len(result.removed)} "
        f"→ {result.feed_count} feeds across {result.folder_count} folders"
    )

    if args.dry_run:
        return 0

    FEEDS_XML.write_text(result.new_feeds_xml, encoding="utf-8")
    README.write_text(result.new_readme, encoding="utf-8")
    CHANGELOG.write_text(result.new_changelog, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
