"""Structural lint for feeds.xml.

Enforces invariants beyond "well-formed XML": flat folder nesting, required
leaf attributes, no duplicate feed URLs, folder naming convention, and
every feed must live inside a folder.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_FOLDER_NAME_RE = re.compile(r"^\d{2} [^\x00-\x7F]")
_REQUIRED_LEAF_ATTRS: tuple[str, ...] = ("xmlUrl", "htmlUrl", "text", "title")


@dataclass(frozen=True)
class LintError:
    """A single structural lint failure."""

    rule: str
    message: str
    location: str


def lint_opml(path: Path) -> list[LintError]:
    """Return structural lint errors for the OPML file at ``path``.

    An empty list means the file satisfies every invariant.
    """
    tree = ET.parse(path)
    body = tree.getroot().find("body")
    if body is None:
        return [LintError("structure", "OPML has no <body>", str(path))]
    errors: list[LintError] = []
    xml_urls: Counter[str] = Counter()
    for child in body:
        if child.tag != "outline":
            continue
        folder_name = child.get("text") or child.get("title") or ""
        errors += _check_folder(child, folder_name)
        for leaf in child:
            if leaf.tag != "outline":
                continue
            if any(c.tag == "outline" for c in leaf):
                continue
            errors += _check_leaf(leaf, folder_name)
            url = (leaf.get("xmlUrl") or "").strip()
            if url:
                xml_urls[url] += 1
    for url, count in xml_urls.items():
        if count > 1:
            errors.append(
                LintError("duplicate-xmlurl", f"{url} appears {count} times", url)
            )
    return errors


def _check_folder(folder: ET.Element, name: str) -> list[LintError]:
    """Return errors specific to a top-level outline treated as a folder."""
    if folder.get("xmlUrl"):
        return [
            LintError(
                "feed-at-body-root",
                f"feed outline must live inside a folder: {name!r}",
                name,
            )
        ]
    errs: list[LintError] = []
    if not _FOLDER_NAME_RE.match(name):
        errs.append(
            LintError(
                "folder-name",
                f"folder name must match '^\\d{{2}} <emoji> ...': {name!r}",
                name,
            )
        )
    for child in folder:
        if child.tag == "outline" and any(c.tag == "outline" for c in child):
            errs.append(
                LintError(
                    "nested-folder",
                    f"folders must be flat; found sub-outline inside {name!r}",
                    name,
                )
            )
            break
    return errs


def _check_leaf(leaf: ET.Element, folder_name: str) -> list[LintError]:
    """Return errors for a single feed leaf outline inside a folder."""
    name = leaf.get("text") or leaf.get("title") or "(unknown)"
    loc = f"{folder_name} :: {name}"
    errs: list[LintError] = []
    for attr in _REQUIRED_LEAF_ATTRS:
        value = (leaf.get(attr) or "").strip()
        if not value:
            errs.append(
                LintError("missing-attribute", f"{attr} is missing or empty", loc)
            )
    if leaf.get("type") != "rss":
        errs.append(
            LintError(
                "wrong-type",
                f"type must be 'rss', got {leaf.get('type')!r}",
                loc,
            )
        )
    return errs


def main() -> int:
    """CLI entry: lint feeds.xml (or a given path) and exit non-zero on errors."""
    parser = argparse.ArgumentParser(description="Lint feeds.xml structure.")
    parser.add_argument("path", nargs="?", default="feeds.xml", type=Path)
    args = parser.parse_args()
    errors = lint_opml(args.path)
    for err in errors:
        print(f"{err.rule}: {err.message} [{err.location}]", file=sys.stderr)
    if errors:
        print(f"{len(errors)} error(s)", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
