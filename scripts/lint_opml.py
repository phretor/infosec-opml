"""Structural lint for feeds.xml.

Enforces invariants beyond "well-formed XML": flat folder nesting, required
leaf attributes, no duplicate feed URLs, folder naming convention, and
every feed must live inside a folder.

Duplicate ``xmlUrl`` values are errors. Comparison follows
``scripts.miniflux_push.url_key`` (scheme, host case, and a trailing slash are
insignificant) and also strips one leading ``www.`` host label. Push and sync
behavior is unchanged; only this lint strips ``www.``.

Duplicate normalized ``htmlUrl`` values, and ``xmlUrl`` values that use
cleartext ``http://``, are warnings. Warnings are printed and do not change
the exit code. One site may legitimately publish more than one feed.

Two www-only aliases already subscribed in Miniflux are warnings rather than
errors while their URL set is unchanged. A contributor PR cannot delete them,
and the next sync would restore a deletion, so failing on them would fail
every PR (including sync) until they are removed in Miniflux. Any other
normalized ``xmlUrl`` collision, including a change to those two groups, is
still an error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

_FOLDER_NAME_RE = re.compile(r"^\d{2} [^\x00-\x7F]")
_REQUIRED_LEAF_ATTRS: tuple[str, ...] = ("xmlUrl", "htmlUrl", "text", "title")

# url_key -> the exact xmlUrl strings currently subscribed for that key.
# Warning, not error, only when the group is still exactly this set.
EXISTING_WWW_ALIASES: dict[str, frozenset[str]] = {
    "//claroty.com/team82/disclosure-dashboard/feed": frozenset(
        {
            "https://claroty.com/team82/disclosure-dashboard/feed",
            "https://www.claroty.com/team82/disclosure-dashboard/feed",
        }
    ),
    "//malwaretech.com/feed": frozenset(
        {
            "https://malwaretech.com/feed",
            "https://www.malwaretech.com/feed",
        }
    ),
}

_Seen = tuple[str, str]


@dataclass(frozen=True)
class LintError:
    """A single structural lint finding. Only ``error`` severity fails the run."""

    rule: str
    message: str
    location: str
    severity: Literal["error", "warning"] = "error"


def url_key(url: str) -> str:
    """Return a comparison key for a feed or site URL.

    Matches ``scripts.miniflux_push.url_key``: the scheme is dropped, the
    netloc is lowercased, a trailing slash is stripped from the path, the
    query is kept, and the fragment is dropped. Also strips one leading
    ``www.`` label from the host. ``miniflux_push.url_key`` does not strip
    ``www.``; that difference is intentional and does not change push.
    """
    parts = urlsplit(url.strip())
    netloc = _without_leading_www(parts.netloc.lower())
    return urlunsplit(("", netloc, parts.path.rstrip("/"), parts.query, ""))


def _without_leading_www(netloc: str) -> str:
    """Drop one leading ``www.`` label from an already-lowercased netloc."""
    userinfo, sep, hostport = netloc.rpartition("@")
    prefix = f"{userinfo}@" if sep else ""
    if hostport.startswith("["):
        return netloc
    host, port_sep, port = hostport.partition(":")
    if host.startswith("www."):
        host = host.removeprefix("www.")
    return f"{prefix}{host}{port_sep}{port}"


def lint_opml(path: Path) -> list[LintError]:
    """Return structural lint findings for the OPML file at ``path``.

    An empty list means the file has no errors and no warnings. Filter on
    ``severity`` to ignore warnings: only ``error`` findings fail CI.
    """
    tree = ET.parse(path)
    body = tree.getroot().find("body")
    if body is None:
        return [LintError("structure", "OPML has no <body>", str(path))]
    errors: list[LintError] = []
    warnings: list[LintError] = []
    xml_by_key: dict[str, list[_Seen]] = defaultdict(list)
    html_by_key: dict[str, list[_Seen]] = defaultdict(list)
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
            name = leaf.get("text") or leaf.get("title") or "(unknown)"
            loc = f"{folder_name} :: {name}"
            url = (leaf.get("xmlUrl") or "").strip()
            if url:
                xml_by_key[url_key(url)].append((url, loc))
                if urlsplit(url).scheme == "http":
                    warnings.append(
                        LintError(
                            "cleartext-xmlurl",
                            f"xmlUrl uses cleartext http://: {url}",
                            loc,
                            "warning",
                        )
                    )
            html = (leaf.get("htmlUrl") or "").strip()
            if html:
                html_by_key[url_key(html)].append((html, loc))
    xml_errors, xml_warnings = _xml_duplicate_findings(xml_by_key)
    errors += xml_errors
    warnings += xml_warnings
    warnings += _duplicate_findings(html_by_key, rule="duplicate-htmlurl", severity="warning")
    return errors + warnings


def _xml_duplicate_findings(
    grouped: dict[str, list[_Seen]],
) -> tuple[list[LintError], list[LintError]]:
    """Split normalized xmlUrl collisions into errors and grandfathered warnings."""
    errors: list[LintError] = []
    warnings: list[LintError] = []
    for finding in _duplicate_findings(grouped, rule="duplicate-xmlurl", severity="error"):
        urls = frozenset(url for url, _loc in grouped[finding.location])
        known = EXISTING_WWW_ALIASES.get(finding.location)
        if known is not None and urls == known:
            warnings.append(
                LintError(
                    finding.rule,
                    finding.message + "; existing Miniflux www alias (warning while unchanged)",
                    finding.location,
                    "warning",
                )
            )
            continue
        errors.append(finding)
    return errors, warnings


def _duplicate_findings(
    grouped: dict[str, list[_Seen]],
    *,
    rule: str,
    severity: Literal["error", "warning"],
) -> list[LintError]:
    """Return one finding per normalized URL that more than one feed uses."""
    findings: list[LintError] = []
    for key, seen in grouped.items():
        if len(seen) < 2:
            continue
        details = "; ".join(f"{url} [{loc}]" for url, loc in seen)
        findings.append(
            LintError(
                rule,
                f"{len(seen)} feeds share a URL after normalization: {details}",
                key,
                severity,
            )
        )
    return findings


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
            errs.append(LintError("missing-attribute", f"{attr} is missing or empty", loc))
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
    """CLI entry: lint feeds.xml (or a given path) and exit non-zero on errors.

    Warnings are printed and do not change the exit code.
    """
    parser = argparse.ArgumentParser(description="Lint feeds.xml structure.")
    parser.add_argument("path", nargs="?", default="feeds.xml", type=Path)
    args = parser.parse_args()
    findings = lint_opml(args.path)
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    for warn in warnings:
        print(f"warning: {warn.rule}: {warn.message} [{warn.location}]", file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::warning title={warn.rule}::{warn.message} [{warn.location}]")
    for err in errors:
        print(f"{err.rule}: {err.message} [{err.location}]", file=sys.stderr)
    if errors:
        print(f"{len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
        return 1
    print(f"OK ({len(warnings)} warning(s))" if warnings else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
