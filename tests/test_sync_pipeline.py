"""Tests for the pure sync pipeline. No HTTP, no filesystem writes."""

from datetime import date
from pathlib import Path

import pytest

from scripts.miniflux_sync import (
    NoChange,
    SyncOutput,
    normalize_opml,
    sync_pipeline,
)

FIXTURES = Path(__file__).parent / "fixtures"
SYNC_DATE = date(2026, 10, 8)


@pytest.fixture
def base_opml() -> str:
    return (FIXTURES / "miniflux_base.opml").read_text(encoding="utf-8")


@pytest.fixture
def current_readme() -> str:
    return (FIXTURES / "current_readme.md").read_text(encoding="utf-8")


@pytest.fixture
def current_changelog() -> str:
    return (FIXTURES / "current_changelog.md").read_text(encoding="utf-8")


@pytest.fixture
def current_feeds_xml(base_opml: str) -> str:
    return normalize_opml(base_opml)


def test_normalize_is_idempotent(base_opml: str) -> None:
    once = normalize_opml(base_opml)
    twice = normalize_opml(once)
    assert once == twice


def test_normalize_fixes_attribute_order_and_indent(base_opml: str) -> None:
    out = normalize_opml(base_opml)
    assert out.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<opml version="1.0">')
    assert "  <body>" in out
    assert '      <outline text="CISA Advisories" title="CISA Advisories" type="rss"' in out


def test_no_change_short_circuits(
    base_opml: str, current_feeds_xml: str, current_readme: str, current_changelog: str
) -> None:
    result = sync_pipeline(
        base_opml, current_feeds_xml, current_readme, current_changelog, SYNC_DATE
    )
    assert isinstance(result, NoChange)


def test_added_folder_adds_feed_and_patches_counts(
    current_feeds_xml: str, current_readme: str, current_changelog: str
) -> None:
    incoming = (FIXTURES / "miniflux_added_folder.opml").read_text(encoding="utf-8")

    result = sync_pipeline(incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE)

    assert isinstance(result, SyncOutput)
    assert len(result.added) == 1
    assert result.added[0].xml_url == "https://claroty.com/team82/feed"
    assert result.added[0].folder == "03 🏭 OT & ICS Security"
    assert result.removed == ()
    assert result.feed_count == 4
    assert result.folder_count == 3
    assert "collection of 4 information security" in result.new_readme
    assert "organized into 3 permanent, flat folders" in result.new_readme
    assert result.new_changelog.startswith("# Changelog")
    assert f"## {SYNC_DATE.isoformat()}" in result.new_changelog
    assert "### Added" in result.new_changelog
    assert "- Claroty Team82 (03 🏭 OT & ICS Security)" in result.new_changelog
    assert "### Removed" not in result.new_changelog.split("## 2026-01-01")[0]


def test_removed_folder_drops_feed(
    current_feeds_xml: str, current_readme: str, current_changelog: str
) -> None:
    incoming = (FIXTURES / "miniflux_removed_folder.opml").read_text(encoding="utf-8")

    result = sync_pipeline(incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE)

    assert isinstance(result, SyncOutput)
    assert result.added == ()
    assert len(result.removed) == 1
    assert result.removed[0].xml_url == "https://risky.biz/feeds/risky-business/"
    assert result.feed_count == 2
    assert result.folder_count == 1
    first_entry = result.new_changelog.split("## 2026-01-01")[0]
    assert "### Removed" in first_entry
    assert "### Added" not in first_entry


def test_url_change_is_removed_plus_added(
    current_feeds_xml: str, current_readme: str, current_changelog: str
) -> None:
    incoming = (FIXTURES / "miniflux_url_change.opml").read_text(encoding="utf-8")

    result = sync_pipeline(incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE)

    assert isinstance(result, SyncOutput)
    assert len(result.added) == 1
    assert len(result.removed) == 1
    assert result.added[0].xml_url == "https://www.cisa.gov/new-path.xml"
    assert result.removed[0].xml_url == "https://www.cisa.gov/all.xml"


def test_empty_category_is_omitted(
    current_feeds_xml: str, current_readme: str, current_changelog: str
) -> None:
    incoming = (FIXTURES / "miniflux_empty_category.opml").read_text(encoding="utf-8")

    result = sync_pipeline(incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE)

    assert isinstance(result, NoChange)


def test_changelog_entry_omitted_when_only_formatting_changed(
    base_opml: str, current_readme: str, current_changelog: str
) -> None:
    """If feeds.xml differs only by formatting (e.g. first-time normalization),
    there's no net add/remove — the CHANGELOG must not grow."""
    unnormalized = base_opml
    result = sync_pipeline(base_opml, unnormalized, current_readme, current_changelog, SYNC_DATE)
    assert isinstance(result, SyncOutput)
    assert result.added == ()
    assert result.removed == ()
    assert result.new_changelog == current_changelog
