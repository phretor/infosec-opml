"""Tests for scripts.lint_opml."""

from pathlib import Path

from scripts.lint_opml import lint_opml

OPML_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<opml version="1.0">\n'
    "<head><title>t</title></head>\n"
    "<body>\n"
)
OPML_FOOTER = "</body>\n</opml>\n"
FOLDER_OPEN = '<outline text="01 \U0001f6a8 Alerts">\n'
FOLDER_CLOSE = "</outline>\n"
VALID_LEAF = (
    '<outline title="Example" text="Example" '
    'xmlUrl="https://example.com/feed" htmlUrl="https://example.com/" '
    'type="rss"></outline>\n'
)


def _write(tmp_path: Path, body_fragment: str) -> Path:
    """Write a minimal OPML document to tmp_path/feeds.xml and return the path."""
    p = tmp_path / "feeds.xml"
    p.write_text(OPML_HEADER + body_fragment + OPML_FOOTER, encoding="utf-8")
    return p


def test_valid_opml_is_clean(tmp_path: Path) -> None:
    p = _write(tmp_path, FOLDER_OPEN + VALID_LEAF + FOLDER_CLOSE)
    assert lint_opml(p) == []


def test_feed_at_body_root_fails(tmp_path: Path) -> None:
    errs = lint_opml(_write(tmp_path, VALID_LEAF))
    assert any(e.rule == "feed-at-body-root" for e in errs)


def test_nested_folder_fails(tmp_path: Path) -> None:
    nested = (
        FOLDER_OPEN
        + '<outline text="sub"><outline text="deep" title="deep" '
        + 'xmlUrl="https://x.example/" htmlUrl="https://x.example/" '
        + 'type="rss"/></outline>\n'
        + FOLDER_CLOSE
    )
    errs = lint_opml(_write(tmp_path, nested))
    assert any(e.rule == "nested-folder" for e in errs)


def test_missing_xmlurl_fails(tmp_path: Path) -> None:
    leaf = (
        '<outline title="e" text="e" htmlUrl="https://x.example/" type="rss"/>'
    )
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "missing-attribute" and "xmlUrl" in e.message for e in errs)


def test_empty_xmlurl_fails(tmp_path: Path) -> None:
    leaf = (
        '<outline title="e" text="e" xmlUrl="" '
        'htmlUrl="https://x.example/" type="rss"/>'
    )
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "missing-attribute" and "xmlUrl" in e.message for e in errs)


def test_duplicate_xmlurl_fails(tmp_path: Path) -> None:
    body = FOLDER_OPEN + VALID_LEAF + VALID_LEAF + FOLDER_CLOSE
    errs = lint_opml(_write(tmp_path, body))
    assert any(e.rule == "duplicate-xmlurl" for e in errs)


def test_wrong_type_fails(tmp_path: Path) -> None:
    leaf = (
        '<outline title="e" text="e" xmlUrl="https://x.example/" '
        'htmlUrl="https://x.example/" type="atom"/>'
    )
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "wrong-type" for e in errs)


def test_missing_type_fails(tmp_path: Path) -> None:
    leaf = (
        '<outline title="e" text="e" xmlUrl="https://x.example/" '
        'htmlUrl="https://x.example/"/>'
    )
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "wrong-type" for e in errs)


def test_missing_htmlurl_fails(tmp_path: Path) -> None:
    leaf = (
        '<outline title="e" text="e" xmlUrl="https://x.example/" type="rss"/>'
    )
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "missing-attribute" and "htmlUrl" in e.message for e in errs)


def test_missing_text_fails(tmp_path: Path) -> None:
    leaf = (
        '<outline title="e" xmlUrl="https://x.example/" '
        'htmlUrl="https://x.example/" type="rss"/>'
    )
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "missing-attribute" and "text" in e.message for e in errs)


def test_missing_title_fails(tmp_path: Path) -> None:
    leaf = (
        '<outline text="e" xmlUrl="https://x.example/" '
        'htmlUrl="https://x.example/" type="rss"/>'
    )
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "missing-attribute" and "title" in e.message for e in errs)


def test_folder_without_number_prefix_fails(tmp_path: Path) -> None:
    body = '<outline text="\U0001f6a8 Alerts">' + VALID_LEAF + "</outline>"
    errs = lint_opml(_write(tmp_path, body))
    assert any(e.rule == "folder-name" for e in errs)


def test_folder_without_emoji_fails(tmp_path: Path) -> None:
    body = '<outline text="01 Alerts">' + VALID_LEAF + "</outline>"
    errs = lint_opml(_write(tmp_path, body))
    assert any(e.rule == "folder-name" for e in errs)


def test_real_feeds_xml_is_clean() -> None:
    """Smoke test: the repo's own feeds.xml must satisfy the lint."""
    errs = lint_opml(Path("feeds.xml"))
    assert errs == [], "\n".join(
        f"{e.rule}: {e.message} [{e.location}]" for e in errs
    )
