"""Tests for the Miniflux-API-driven feed health classifier."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts import check_feeds


def _mock_client(feeds_payload: list[dict]) -> httpx.Client:
    """Return an httpx.Client whose /v1/feeds returns the given payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/feeds"
        assert request.headers.get("X-Auth-Token") == "test-token"
        return httpx.Response(200, content=json.dumps(feeds_payload))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_classify_ok() -> None:
    status = check_feeds.MinifluxStatus(disabled=False, parsing_error_count=0, parsing_error_message="")
    assert check_feeds.classify(status, min_error_count=3) == "ok"


def test_classify_transient_below_threshold() -> None:
    status = check_feeds.MinifluxStatus(disabled=False, parsing_error_count=2, parsing_error_message="boom")
    assert check_feeds.classify(status, min_error_count=3) == "transient"


def test_classify_dead_at_threshold() -> None:
    status = check_feeds.MinifluxStatus(disabled=False, parsing_error_count=3, parsing_error_message="boom")
    assert check_feeds.classify(status, min_error_count=3) == "dead"


def test_classify_dead_when_disabled_regardless_of_count() -> None:
    status = check_feeds.MinifluxStatus(disabled=True, parsing_error_count=0, parsing_error_message="")
    assert check_feeds.classify(status, min_error_count=3) == "dead"


def test_classify_dead_when_missing_from_miniflux() -> None:
    assert check_feeds.classify(None, min_error_count=3) == "dead"


def test_fetch_miniflux_feeds_builds_map() -> None:
    client = _mock_client(
        [
            {
                "feed_url": "https://a.example/feed",
                "disabled": False,
                "parsing_error_count": 0,
                "parsing_error_message": "",
            },
            {
                "feed_url": "https://b.example/feed",
                "disabled": True,
                "parsing_error_count": 5,
                "parsing_error_message": "gone",
            },
        ]
    )
    result = check_feeds.fetch_miniflux_feeds("https://mf.example", "test-token", client=client)
    assert set(result) == {"https://a.example/feed", "https://b.example/feed"}
    assert result["https://b.example/feed"].disabled is True
    assert result["https://b.example/feed"].parsing_error_count == 5


def _write_feeds_xml(path: Path, urls_with_folders: list[tuple[str, str, str]]) -> None:
    """Write a minimal feeds.xml with [(name, xmlUrl, folder), ...]."""
    folders: dict[str, list[tuple[str, str]]] = {}
    for name, url, folder in urls_with_folders:
        folders.setdefault(folder, []).append((name, url))
    body_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<opml version="1.0">']
    body_parts.append("  <head><title>t</title></head>")
    body_parts.append("  <body>")
    for folder, feeds in folders.items():
        body_parts.append(f'    <outline text="{folder}">')
        for name, url in feeds:
            body_parts.append(
                f'      <outline text="{name}" type="rss" xmlUrl="{url}" htmlUrl="{url}"></outline>'
            )
        body_parts.append("    </outline>")
    body_parts.append("  </body>")
    body_parts.append("</opml>")
    path.write_text("\n".join(body_parts) + "\n", encoding="utf-8")


def test_fail_on_dead_exit_code_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("Broken", "https://x.example/feed", "01 Test")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.example")
    monkeypatch.setenv("MINIFLUX_TOKEN", "test-token")

    def fake_fetch(base: str, token: str) -> dict[str, check_feeds.MinifluxStatus]:
        return {
            "https://x.example/feed": check_feeds.MinifluxStatus(
                disabled=True, parsing_error_count=0, parsing_error_message=""
            )
        }

    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", fake_fetch)
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])

    with pytest.raises(SystemExit) as exc:
        check_feeds.main()
    assert exc.value.code == 1


def test_fail_on_dead_exit_code_over_threshold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("Flaky", "https://y.example/feed", "01 Test")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.example")
    monkeypatch.setenv("MINIFLUX_TOKEN", "test-token")

    def fake_fetch(base: str, token: str) -> dict[str, check_feeds.MinifluxStatus]:
        return {
            "https://y.example/feed": check_feeds.MinifluxStatus(
                disabled=False, parsing_error_count=5, parsing_error_message="404"
            )
        }

    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", fake_fetch)
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead", "--min-error-count", "3"])

    with pytest.raises(SystemExit) as exc:
        check_feeds.main()
    assert exc.value.code == 1


def test_fail_on_dead_exit_code_missing_from_miniflux(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("Ghost", "https://z.example/feed", "01 Test")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.example")
    monkeypatch.setenv("MINIFLUX_TOKEN", "test-token")
    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", lambda *a, **k: {})
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])

    with pytest.raises(SystemExit) as exc:
        check_feeds.main()
    assert exc.value.code == 1


def test_fail_on_dead_passes_when_all_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("Healthy", "https://ok.example/feed", "01 Test")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.example")
    monkeypatch.setenv("MINIFLUX_TOKEN", "test-token")

    def fake_fetch(base: str, token: str) -> dict[str, check_feeds.MinifluxStatus]:
        return {
            "https://ok.example/feed": check_feeds.MinifluxStatus(
                disabled=False, parsing_error_count=0, parsing_error_message=""
            )
        }

    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", fake_fetch)
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])

    assert check_feeds.main() is None


def test_transient_does_not_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("Flaky", "https://flake.example/feed", "01 Test")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.example")
    monkeypatch.setenv("MINIFLUX_TOKEN", "test-token")

    def fake_fetch(base: str, token: str) -> dict[str, check_feeds.MinifluxStatus]:
        return {
            "https://flake.example/feed": check_feeds.MinifluxStatus(
                disabled=False, parsing_error_count=1, parsing_error_message="single blip"
            )
        }

    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", fake_fetch)
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead", "--min-error-count", "3"])

    assert check_feeds.main() is None


def test_main_errors_without_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("x", "https://x.example/feed", "f")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])

    with pytest.raises(SystemExit) as exc:
        check_feeds.main()
    assert exc.value.code == 2
