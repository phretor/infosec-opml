"""PR gate: a contributor PR may only add feeds to existing folders of feeds.xml.

Miniflux is the source of truth. Merged additions are pushed into Miniflux by
`scripts.miniflux_push`; removals, moves, renames, and metadata edits are not, so the next
Miniflux sync would silently revert them. Those changes go through an issue instead.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, fields
from pathlib import Path

from scripts.miniflux_sync import Feed, parse_opml


@dataclass(frozen=True)
class GateError:
    """A single additions-only violation."""

    rule: str
    message: str


def check_additions(base: list[Feed], head: list[Feed]) -> list[GateError]:
    """Return violations of the additions-only rule between base and head feed lists.

    An empty list means head equals base plus zero or more new feeds in folders base already has.
    """
    base_by_url = {f.xml_url: f for f in base}
    head_by_url = {f.xml_url: f for f in head}
    base_folders = {f.folder for f in base}
    errors: list[GateError] = []
    for url, old in base_by_url.items():
        new = head_by_url.get(url)
        if new is None:
            errors.append(
                GateError("removed-feed", f"{old.name!r} ({old.folder}) was removed: {url}")
            )
        elif new != old:
            changed = [
                fl.name for fl in fields(Feed) if getattr(old, fl.name) != getattr(new, fl.name)
            ]
            errors.append(
                GateError(
                    "changed-feed",
                    f"{old.name!r} ({old.folder}) changed {', '.join(changed)}: {url}",
                )
            )
    for url, new in head_by_url.items():
        if url not in base_by_url and new.folder not in base_folders:
            errors.append(
                GateError(
                    "new-folder",
                    f"{new.name!r} is in folder {new.folder!r}, which does not exist yet: {url}",
                )
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    """CLI entry: compare a PR's feeds.xml against the base branch's copy."""
    parser = argparse.ArgumentParser(
        description="Fail unless feeds.xml only adds feeds to existing folders."
    )
    parser.add_argument("--base", required=True, type=Path, help="feeds.xml on the base branch")
    parser.add_argument("head", nargs="?", default=Path("feeds.xml"), type=Path)
    args = parser.parse_args(argv)
    base = parse_opml(args.base.read_text(encoding="utf-8"))
    head = parse_opml(args.head.read_text(encoding="utf-8"))
    errors = check_additions(base, head)
    for err in errors:
        print(f"{err.rule}: {err.message}", file=sys.stderr)
    if errors:
        print(
            f"{len(errors)} error(s). Pull requests may only add feeds to existing folders; "
            "open an issue to remove, move, or fix a feed (see CONTRIBUTING.md).",
            file=sys.stderr,
        )
        return 1
    added = len({f.xml_url for f in head} - {f.xml_url for f in base})
    print(f"OK: {added} feed(s) added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
