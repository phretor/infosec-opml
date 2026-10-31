"""Verify README.md stays in sync with feeds.xml.

Checks the two sync-anchor sentences (feed count, folder count) and
the folder table against the current OPML. Fails when they drift, except
that a feeds.xml folder not yet listed in the README table is only a
warning: Miniflux syncs add or rename categories before the README catches up.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_FEED_COUNT_RE = re.compile(r"collection of (\d+) information security")
_FOLDER_COUNT_RE = re.compile(r"organized into (\d+) permanent, flat folders")
_TABLE_ROW_RE = re.compile(r"^\|\s*(\d{2} [^|]+?)\s*\|.*\|$", re.MULTILINE)


@dataclass(frozen=True)
class LintError:
    """A single README-consistency finding; only ``error`` severity fails."""

    rule: str
    message: str
    severity: Literal["error", "warning"] = "error"


def check_readme(readme_path: Path, opml_path: Path) -> list[LintError]:
    """Return consistency findings between README.md and feeds.xml.

    An empty list means the two files agree on feed count, folder count,
    and the set of folder names.
    """
    readme = readme_path.read_text(encoding="utf-8")
    opml_folders, opml_feed_count = _parse_opml(opml_path)
    findings: list[LintError] = []
    findings += _check_count(readme, _FEED_COUNT_RE, opml_feed_count, "feed")
    findings += _check_count(readme, _FOLDER_COUNT_RE, len(opml_folders), "folder")
    findings += _check_folder_set(readme, opml_folders)
    return findings


def _parse_opml(opml_path: Path) -> tuple[set[str], int]:
    """Return the folder-name set and total feed count from the OPML file."""
    tree = ET.parse(opml_path)
    body = tree.getroot().find("body")
    folders: set[str] = set()
    feed_count = 0
    if body is None:
        return folders, feed_count
    for child in body:
        if child.tag != "outline":
            continue
        name = child.get("text") or child.get("title")
        if name:
            folders.add(name)
        for leaf in child:
            if leaf.tag == "outline" and leaf.get("xmlUrl"):
                feed_count += 1
    return folders, feed_count


def _check_count(
    readme: str, pattern: re.Pattern[str], expected: int, label: str
) -> list[LintError]:
    """Return a count-mismatch error when README's anchor number differs."""
    match = pattern.search(readme)
    if match is None:
        return [
            LintError(
                f"readme-{label}-count-missing",
                f"README is missing the {label}-count anchor sentence",
            )
        ]
    actual = int(match.group(1))
    if actual != expected:
        return [
            LintError(
                f"readme-{label}-count-mismatch",
                f"README says {actual} {label}(s); feeds.xml has {expected}",
            )
        ]
    return []


def _check_folder_set(readme: str, opml_folders: set[str]) -> list[LintError]:
    """Return findings for folders in only README or only feeds.xml.

    A feeds.xml folder missing from the README is a warning; a README row
    naming a folder that feeds.xml lacks is an error.
    """
    readme_folders = {m.group(1).strip() for m in _TABLE_ROW_RE.finditer(readme)}
    findings: list[LintError] = []
    for name in sorted(opml_folders - readme_folders):
        findings.append(
            LintError(
                "readme-folder-missing",
                f"folder in feeds.xml is not listed in README table: {name!r}",
                "warning",
            )
        )
    for name in sorted(readme_folders - opml_folders):
        findings.append(
            LintError(
                "readme-folder-extra",
                f"folder in README table is not in feeds.xml: {name!r}",
            )
        )
    return findings


def main() -> int:
    """CLI entry: verify README.md agrees with feeds.xml."""
    parser = argparse.ArgumentParser(description="Check README.md against feeds.xml.")
    parser.add_argument("--readme", default=Path("README.md"), type=Path)
    parser.add_argument("--opml", default=Path("feeds.xml"), type=Path)
    args = parser.parse_args()
    findings = check_readme(args.readme, args.opml)
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    for warn in warnings:
        print(f"warning: {warn.rule}: {warn.message}", file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::warning title={warn.rule}::{warn.message}")
    for err in errors:
        print(f"{err.rule}: {err.message}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
        return 1
    print(f"OK ({len(warnings)} warning(s))" if warnings else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
