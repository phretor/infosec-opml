"""Tests for the Miniflux-API-driven feed health classifier."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts import check_feeds
from scripts.check_feeds import MinifluxStatus


def _status(disabled: bool = False, count: int = 0, msg: str = "") -> MinifluxStatus:
    return MinifluxStatus(
        disabled=disabled, parsing_error_count=count, parsing_error_message=msg
    )


def _mock_client(feeds_payload: list[dict]) -> httpx.Client:
    """Return an httpx.Client whose /v1/feeds returns the given payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/feeds"
        assert request.headers.get("X-Auth-Token") == "test-token"
        return httpx.Response(200, content=json.dumps(feeds_payload))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_classify_ok() -> None:
    assert check_feeds.classify(_status(), min_error_count=3) == "ok"


def test_classify_transient_below_threshold() -> None:
    assert check_feeds.classify(_status(count=2, msg="boom"), min_error_count=3) == "transient"


def test_classify_dead_at_threshold() -> None:
    assert check_feeds.classify(_status(count=3, msg="boom"), min_error_count=3) == "dead"


def test_classify_dead_when_disabled_regardless_of_count() -> None:
    assert check_feeds.classify(_status(disabled=True), min_error_count=3) == "dead"


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
    result = check_feeds.fetch_miniflux_feeds(
        "https://mf.example", "test-token", client=client
    )
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
                f'      <outline text="{name}" type="rss" '
                f'xmlUrl="{url}" htmlUrl="{url}"></outline>'
            )
        body_parts.append("    </outline>")
    body_parts.append("  </body>")
    body_parts.append("</opml>")
    path.write_text("\n".join(body_parts) + "\n", encoding="utf-8")


_TEST_URL = "https://x.example/feed"


@pytest.mark.parametrize(
    ("miniflux_payload", "expected_exit"),
    [
        pytest.param({_TEST_URL: _status(disabled=True)}, 1, id="disabled"),
        pytest.param({_TEST_URL: _status(count=5, msg="404")}, 1, id="over-threshold"),
        pytest.param({}, 1, id="missing-from-miniflux"),
        pytest.param({_TEST_URL: _status()}, None, id="ok"),
        pytest.param(
            {_TEST_URL: _status(count=1, msg="single blip")}, None, id="transient"
        ),
    ],
)
def test_fail_on_dead_exit_matrix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    miniflux_payload: dict[str, MinifluxStatus],
    expected_exit: int | None,
) -> None:
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("Feed", _TEST_URL, "01 Test")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.example")
    monkeypatch.setenv("MINIFLUX_TOKEN", "test-token")
    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", lambda *a, **k: miniflux_payload)
    monkeypatch.setattr(
        "sys.argv", ["check_feeds", "--fail-on-dead", "--min-error-count", "3"]
    )

    if expected_exit is None:
        assert check_feeds.main() is None
    else:
        with pytest.raises(SystemExit) as exc:
            check_feeds.main()
        assert exc.value.code == expected_exit


def test_main_errors_without_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("x", "https://x.example/feed", "f")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])

    with pytest.raises(SystemExit) as exc:
        check_feeds.main()
    assert exc.value.code == 2
