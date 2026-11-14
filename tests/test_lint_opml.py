"""Tests for scripts.lint_opml."""

from pathlib import Path

import pytest

from scripts.lint_opml import EXISTING_WWW_ALIASES, lint_opml, main, url_key
from scripts.miniflux_push import url_key as push_url_key

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
    leaf = '<outline title="e" text="e" htmlUrl="https://x.example/" type="rss"/>'
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "missing-attribute" and "xmlUrl" in e.message for e in errs)


def test_empty_xmlurl_fails(tmp_path: Path) -> None:
    leaf = '<outline title="e" text="e" xmlUrl="" htmlUrl="https://x.example/" type="rss"/>'
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
    leaf = '<outline title="e" text="e" xmlUrl="https://x.example/" htmlUrl="https://x.example/"/>'
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "wrong-type" for e in errs)


def test_missing_htmlurl_fails(tmp_path: Path) -> None:
    leaf = '<outline title="e" text="e" xmlUrl="https://x.example/" type="rss"/>'
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "missing-attribute" and "htmlUrl" in e.message for e in errs)


def test_missing_text_fails(tmp_path: Path) -> None:
    leaf = (
        '<outline title="e" xmlUrl="https://x.example/" htmlUrl="https://x.example/" type="rss"/>'
    )
    errs = lint_opml(_write(tmp_path, FOLDER_OPEN + leaf + FOLDER_CLOSE))
    assert any(e.rule == "missing-attribute" and "text" in e.message for e in errs)


def test_missing_title_fails(tmp_path: Path) -> None:
    leaf = '<outline text="e" xmlUrl="https://x.example/" htmlUrl="https://x.example/" type="rss"/>'
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


def _leaf(xml_url: str, html_url: str, name: str = "Example") -> str:
    return (
        f'<outline title="{name}" text="{name}" '
        f'xmlUrl="{xml_url}" htmlUrl="{html_url}" type="rss"></outline>\n'
    )


def _run_main(monkeypatch: pytest.MonkeyPatch, path: Path) -> int:
    monkeypatch.setattr("sys.argv", ["lint_opml", str(path)])
    return main()


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("https://example.com/feed", "http://example.com/feed"),
        ("https://Example.COM/feed", "https://example.com/feed"),
        ("https://www.example.com/feed", "https://example.com/feed"),
        ("https://example.com/feed/", "https://example.com/feed"),
        ("https://example.com/feed#section", "https://example.com/feed"),
        ("http://WWW.Example.com/feed/", "https://example.com/feed"),
    ],
)
def test_normalized_xmlurl_duplicate_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, left: str, right: str
) -> None:
    body = (
        FOLDER_OPEN
        + _leaf(left, "https://left.example/")
        + _leaf(right, "https://right.example/", "Other")
        + FOLDER_CLOSE
    )
    findings = lint_opml(_write(tmp_path, body))
    errors = [e for e in findings if e.severity == "error"]
    assert [e.rule for e in errors] == ["duplicate-xmlurl"]
    assert _run_main(monkeypatch, _write(tmp_path, body)) == 1


def test_distinct_feed_urls_are_not_duplicates(tmp_path: Path) -> None:
    urls = [
        "https://example.com/feed",
        "https://example.com/other",
        "https://example.com/feed?alt=rss",
        "https://blog.example.com/feed",
        "https://www2.example.com/feed",
        "https://notwww.example.com/feed",
    ]
    body = FOLDER_OPEN
    for i, url in enumerate(urls):
        body += _leaf(url, f"https://site{i}.example/", f"Feed{i}")
    body += FOLDER_CLOSE
    assert lint_opml(_write(tmp_path, body)) == []


def test_duplicate_htmlurl_is_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    body = (
        FOLDER_OPEN
        + _leaf("https://a.example/feed", "http://www.shared.example/site/")
        + _leaf("https://b.example/feed", "https://shared.example/site", "Other")
        + FOLDER_CLOSE
    )
    path = _write(tmp_path, body)
    findings = lint_opml(path)
    assert [(f.rule, f.severity) for f in findings] == [("duplicate-htmlurl", "warning")]
    assert _run_main(monkeypatch, path) == 0
    assert "warning: duplicate-htmlurl:" in capsys.readouterr().err


def test_cleartext_xmlurl_is_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    body = FOLDER_OPEN + _leaf("HTTP://example.com/feed", "https://example.com/") + FOLDER_CLOSE
    path = _write(tmp_path, body)
    findings = lint_opml(path)
    assert [(f.rule, f.severity) for f in findings] == [("cleartext-xmlurl", "warning")]
    assert _run_main(monkeypatch, path) == 0
    captured = capsys.readouterr().err
    assert "warning: cleartext-xmlurl:" in captured
    assert "error(s)" not in captured


def test_warnings_do_not_change_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = (
        FOLDER_OPEN
        + _leaf("http://example.com/feed", "https://shared.example/")
        + _leaf("https://other.example/feed", "https://www.shared.example", "Other")
        + FOLDER_CLOSE
    )
    path = _write(tmp_path, body)
    findings = lint_opml(path)
    assert [(f.rule, f.severity) for f in findings] == [
        ("cleartext-xmlurl", "warning"),
        ("duplicate-htmlurl", "warning"),
    ]
    assert _run_main(monkeypatch, path) == 0


def test_warning_does_not_mask_duplicate_xmlurl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = (
        FOLDER_OPEN
        + _leaf("http://www.example.com/feed/", "https://shared.example/")
        + _leaf("https://example.com/feed", "https://shared.example/", "Other")
        + FOLDER_CLOSE
    )
    path = _write(tmp_path, body)
    findings = lint_opml(path)
    assert [e.rule for e in findings if e.severity == "error"] == ["duplicate-xmlurl"]
    assert any(e.rule == "cleartext-xmlurl" and e.severity == "warning" for e in findings)
    assert any(e.rule == "duplicate-htmlurl" and e.severity == "warning" for e in findings)
    assert _run_main(monkeypatch, path) == 1


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/feed",
        "http://Example.COM/feed/",
        "https://example.com/feed?x=1",
        "https://example.com/feed#frag",
        "https://user:pass@example.com:8443/a/b/",
        "https://blog.example.com/www.feed",
    ],
)
def test_url_key_matches_miniflux_push_without_www(url: str) -> None:
    assert url_key(url) == push_url_key(url)


def test_url_key_strips_one_leading_www_label() -> None:
    assert url_key("https://www.example.com/feed") == url_key("https://example.com/feed")
    assert url_key("https://WWW.Example.com/feed/") == url_key("https://example.com/feed")
    # One leading label only: www.www.example.com becomes www.example.com.
    assert url_key("https://www.www.example.com/feed") == "//www.example.com/feed"
    assert url_key("https://www.example.com/feed") != push_url_key("https://www.example.com/feed")
    assert url_key("https://www2.example.com/feed") != url_key("https://example.com/feed")


def test_existing_www_alias_warns_until_the_url_set_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = "//malwaretech.com/feed"
    urls = sorted(EXISTING_WWW_ALIASES[key])
    body = (
        FOLDER_OPEN
        + _leaf(urls[0], "https://a.example/", "A")
        + _leaf(urls[1], "https://b.example/", "B")
        + FOLDER_CLOSE
    )
    path = _write(tmp_path, body)
    findings = lint_opml(path)
    assert [(f.rule, f.severity) for f in findings] == [("duplicate-xmlurl", "warning")]
    assert _run_main(monkeypatch, path) == 0


def test_existing_www_alias_becomes_an_error_when_another_url_joins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls = sorted(EXISTING_WWW_ALIASES["//malwaretech.com/feed"])
    body = (
        FOLDER_OPEN
        + _leaf(urls[0], "https://a.example/", "A")
        + _leaf(urls[1], "https://b.example/", "B")
        + _leaf("http://malwaretech.com/feed", "https://c.example/", "C")
        + FOLDER_CLOSE
    )
    path = _write(tmp_path, body)
    findings = lint_opml(path)
    assert [e.rule for e in findings if e.severity == "error"] == ["duplicate-xmlurl"]
    assert _run_main(monkeypatch, path) == 1


def test_real_feeds_xml_has_no_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke test: feeds.xml has no lint errors and the CLI exits 0.

    The two pre-existing www aliases are warnings. Duplicate htmlUrl values
    and cleartext xmlUrl values are warnings too. None of them fail this test.
    """
    findings = lint_opml(Path("feeds.xml"))
    errors = [e for e in findings if e.severity == "error"]
    warnings = [e for e in findings if e.severity == "warning"]
    assert errors == [], "\n".join(f"{e.rule}: {e.message} [{e.location}]" for e in errors)
    assert _run_main(monkeypatch, Path("feeds.xml")) == 0
    assert {e.rule for e in warnings} <= {
        "duplicate-htmlurl",
        "cleartext-xmlurl",
        "duplicate-xmlurl",
    }
    text = Path("feeds.xml").read_text(encoding="utf-8")
    expected = {
        key for key, urls in EXISTING_WWW_ALIASES.items() if all(url in text for url in urls)
    }
    got = {e.location for e in warnings if e.rule == "duplicate-xmlurl"}
    assert got == expected
