"""Tests for the pure sync pipeline. No HTTP, no filesystem writes."""

import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest

from scripts.miniflux_sync import (
    NoChange,
    SyncOutput,
    normalize_opml,
    patch_readme,
    sync_pipeline,
)

FIXTURES = Path(__file__).parent / "fixtures"
SYNC_DATE = date(2026, 10, 8)


def _reverse_order(opml_text: str) -> str:
    """Return the same OPML with folders and feeds in reverse source order."""
    root = ET.fromstring(opml_text)
    body = root.find("body")
    assert body is not None
    for folder in list(body):
        children = list(folder)
        for child in children:
            folder.remove(child)
        for child in reversed(children):
            folder.append(child)
    folders = list(body)
    for folder in folders:
        body.remove(folder)
    for folder in reversed(folders):
        body.append(folder)
    return ET.tostring(root, encoding="unicode")


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

    result = sync_pipeline(
        incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE
    )

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

    result = sync_pipeline(
        incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE
    )

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

    result = sync_pipeline(
        incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE
    )

    assert isinstance(result, SyncOutput)
    assert len(result.added) == 1
    assert len(result.removed) == 1
    assert result.added[0].xml_url == "https://www.cisa.gov/new-path.xml"
    assert result.removed[0].xml_url == "https://www.cisa.gov/all.xml"


def test_empty_category_is_omitted(
    current_feeds_xml: str, current_readme: str, current_changelog: str
) -> None:
    incoming = (FIXTURES / "miniflux_empty_category.opml").read_text(encoding="utf-8")

    result = sync_pipeline(
        incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE
    )

    assert isinstance(result, NoChange)


def test_patch_readme_raises_on_missing_anchor() -> None:
    """A README that doesn't contain the expected sentences must fail loudly,
    not silently emit stale counts."""
    broken_readme = "# Totally different README\n\nNo anchor sentences here.\n"
    with pytest.raises(ValueError, match="anchor"):
        patch_readme(broken_readme, 1, 1)


def test_normalize_emits_canonical_order(base_opml: str) -> None:
    """Folders sort by text; feeds sort case-insensitively by text."""
    out = normalize_opml(_reverse_order(base_opml))
    assert out == normalize_opml(base_opml)
    assert out.index('text="01 🚨 Alerts') < out.index('text="02 📩 Curated')
    assert out.index('text="CISA Advisories"') < out.index('text="Full Disclosure"')


def test_reordered_response_produces_byte_identical_feeds_xml(base_opml: str) -> None:
    """A Miniflux response that only reorders folders/feeds normalizes identically."""
    canonical = normalize_opml(base_opml)
    assert normalize_opml(_reverse_order(base_opml)) == canonical


def test_same_named_feeds_sort_by_xml_url() -> None:
    """Duplicate display names are ordered by xmlUrl so ties are deterministic."""
    opml = (
        '<?xml version="1.0"?><opml version="2.0"><body>'
        '<outline text="01 🚨 Alerts &amp; Advisories">'
        '<outline text="Same" title="Same" type="rss" '
        'xmlUrl="https://b.example/feed" htmlUrl="https://b.example/"></outline>'
        '<outline text="Same" title="Same" type="rss" '
        'xmlUrl="https://a.example/feed" htmlUrl="https://a.example/"></outline>'
        "</outline></body></opml>"
    )
    out = normalize_opml(opml)
    assert out.index("https://a.example/feed") < out.index("https://b.example/feed")


def test_feed_sort_is_case_insensitive() -> None:
    opml = (
        '<?xml version="1.0"?><opml version="2.0"><body>'
        '<outline text="01 🚨 Alerts &amp; Advisories">'
        '<outline text="zeta" title="zeta" type="rss" '
        'xmlUrl="https://z.example/feed" htmlUrl="https://z.example/"></outline>'
        '<outline text="Alpha" title="Alpha" type="rss" '
        'xmlUrl="https://a.example/feed" htmlUrl="https://a.example/"></outline>'
        "</outline></body></opml>"
    )
    out = normalize_opml(opml)
    assert out.index('text="Alpha"') < out.index('text="zeta"')


def test_order_only_difference_is_no_change(
    base_opml: str, current_feeds_xml: str, current_readme: str, current_changelog: str
) -> None:
    """A reordered response must return NoChange so the workflow opens no PR."""
    result = sync_pipeline(
        _reverse_order(base_opml),
        current_feeds_xml,
        current_readme,
        current_changelog,
        SYNC_DATE,
    )
    assert isinstance(result, NoChange)


def test_unnormalized_current_file_is_no_change(
    base_opml: str, current_readme: str, current_changelog: str
) -> None:
    """Formatting/order drift in the current file alone must not open a PR."""
    result = sync_pipeline(
        base_opml,
        _reverse_order(base_opml),
        current_readme,
        current_changelog,
        SYNC_DATE,
    )
    assert isinstance(result, NoChange)


def test_reorder_plus_addition_is_detected(
    current_feeds_xml: str, current_readme: str, current_changelog: str
) -> None:
    incoming = _reverse_order((FIXTURES / "miniflux_added_folder.opml").read_text(encoding="utf-8"))

    result = sync_pipeline(
        incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE
    )

    assert isinstance(result, SyncOutput)
    assert [f.xml_url for f in result.added] == ["https://claroty.com/team82/feed"]
    assert result.removed == ()
    assert result.feed_count == 4
    assert result.folder_count == 3
    assert result.new_feeds_xml == normalize_opml(incoming)
    assert "### Added" in result.new_changelog.split("## 2026-01-01")[0]


def test_reorder_plus_removal_is_detected(
    current_feeds_xml: str, current_readme: str, current_changelog: str
) -> None:
    incoming = _reverse_order(
        (FIXTURES / "miniflux_removed_folder.opml").read_text(encoding="utf-8")
    )

    result = sync_pipeline(
        incoming, current_feeds_xml, current_readme, current_changelog, SYNC_DATE
    )

    assert isinstance(result, SyncOutput)
    assert result.added == ()
    assert [f.xml_url for f in result.removed] == ["https://risky.biz/feeds/risky-business/"]
    assert result.feed_count == 2
    assert result.folder_count == 1
    assert result.new_feeds_xml == normalize_opml(incoming)
    assert "### Removed" in result.new_changelog.split("## 2026-01-01")[0]
