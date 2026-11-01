"""Tests for the Miniflux-API-driven feed health classifier."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts import check_feeds
from scripts.check_feeds import MinifluxStatus


def _status(disabled: bool = False, count: int = 0, msg: str = "") -> MinifluxStatus:
    return MinifluxStatus(disabled=disabled, parsing_error_count=count, parsing_error_message=msg)


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


_TEST_URL = "https://x.example/feed"


@pytest.mark.parametrize(
    ("miniflux_payload", "expected_exit"),
    [
        pytest.param({_TEST_URL: _status(disabled=True)}, 1, id="disabled"),
        pytest.param({_TEST_URL: _status(count=5, msg="404")}, 1, id="over-threshold"),
        pytest.param({}, 1, id="missing-from-miniflux"),
        pytest.param({_TEST_URL: _status()}, None, id="ok"),
        pytest.param({_TEST_URL: _status(count=1, msg="single blip")}, None, id="transient"),
        pytest.param(
            {
                _TEST_URL: _status(
                    count=5,
                    msg="Miniflux is not able to reach this website due to a network "
                    "error: dial tcp: i/o timeout.",
                )
            },
            None,
            id="over-threshold-unreachable",
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
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead", "--min-error-count", "3"])

    if expected_exit is None:
        assert check_feeds.main() is None
    else:
        with pytest.raises(SystemExit) as exc:
            check_feeds.main()
        assert exc.value.code == expected_exit


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


# Real Miniflux en_US parsing_error_message strings (see is_transient_unreachable).
_NETWORK_ERR = (
    "Miniflux is not able to reach this website due to a network error: "
    'Get "https://x.example/feed": dial tcp: lookup x.example: no such host.'
)
_TIMEOUT_ERR = "This website is too slow and the request timed out: context deadline exceeded"
_TOO_MANY = (
    "Miniflux generated too many requests to this website. Please, try again later "
    "or change the application configuration."
)
_BAD_GATEWAY = (
    "The website is not available at the moment due to a bad gateway error. "
    "The problem is not on Miniflux side. Please, try again later."
)
_SERVER_ERR = (
    "The website is not available at the moment due to a server error. "
    "The problem is not on Miniflux side. Please, try again later."
)


def _unexpected_status(code: int) -> str:
    return (
        "The website is not available at the moment due to an unexpected HTTP status "
        f"code: {code}. The problem is not on Miniflux side. Please, try again later."
    )


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        pytest.param(_NETWORK_ERR, "unreachable", id="network-dns"),
        pytest.param(_TIMEOUT_ERR, "unreachable", id="timeout"),
        pytest.param(_TOO_MANY, "unreachable", id="429"),
        pytest.param(_BAD_GATEWAY, "unreachable", id="502"),
        pytest.param(_SERVER_ERR, "unreachable", id="500"),
        pytest.param(_unexpected_status(522), "unreachable", id="522"),
        pytest.param(_unexpected_status(410), "dead", id="410-unexpected-status"),
        pytest.param(
            "The requested resource is not found. Please, verify the URL.",
            "dead",
            id="404",
        ),
        pytest.param(
            "Access to this website is forbidden. Perhaps, this website has a bot "
            "protection mechanism?",
            "dead",
            id="403",
        ),
        pytest.param("This feed already exists.", "dead", id="already-exists"),
        pytest.param("Unable to detect feed format: EOF.", "dead", id="parse-error"),
    ],
)
def test_classify_over_threshold_by_message(message: str, expected: str) -> None:
    assert check_feeds.classify(_status(count=3, msg=message), min_error_count=3) == expected


def test_classify_disabled_stays_dead_even_when_unreachable() -> None:
    status = _status(disabled=True, count=5, msg=_NETWORK_ERR)
    assert check_feeds.classify(status, min_error_count=3) == "dead"


def _main_with_fetch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fetch) -> None:
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("Feed", _TEST_URL, "01 Test")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.example")
    monkeypatch.setenv("MINIFLUX_TOKEN", "test-token")
    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", fetch)
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])
    return check_feeds.main()


def _raising_fetch(exc: Exception):
    def fetch(*_a, **_k):
        raise exc

    return fetch


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://mf.example/v1/feeds")
    return httpx.HTTPStatusError(
        "boom", request=request, response=httpx.Response(code, request=request)
    )


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(httpx.ConnectError("refused"), id="connect-error"),
        pytest.param(httpx.ReadTimeout("slow"), id="timeout"),
        pytest.param(_status_error(503), id="503"),
        pytest.param(_status_error(429), id="429"),
    ],
)
def test_transient_miniflux_api_failure_does_not_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, exc: Exception
) -> None:
    assert _main_with_fetch(monkeypatch, tmp_path, _raising_fetch(exc)) is None


def test_miniflux_auth_failure_still_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with pytest.raises(httpx.HTTPStatusError):
        _main_with_fetch(monkeypatch, tmp_path, _raising_fetch(_status_error(401)))


_BASE_URL = "https://old.example/feed"
_NEW_URL = "https://new.example/feed"


@pytest.mark.parametrize(
    ("miniflux_payload", "expected_exit"),
    [
        pytest.param({_BASE_URL: _status()}, None, id="new-feed-missing-is-pending"),
        pytest.param({_NEW_URL: _status()}, 1, id="base-feed-missing-stays-dead"),
    ],
)
def test_base_opml_marks_new_feeds_missing_from_miniflux_pending(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    miniflux_payload: dict[str, MinifluxStatus],
    expected_exit: int | None,
) -> None:
    base_xml = tmp_path / "base.xml"
    _write_feeds_xml(base_xml, [("Old", _BASE_URL, "01 Test")])
    feeds_xml = tmp_path / "feeds.xml"
    _write_feeds_xml(feeds_xml, [("Old", _BASE_URL, "01 Test"), ("New", _NEW_URL, "01 Test")])
    monkeypatch.setattr(check_feeds, "FEEDS_XML", feeds_xml)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.example")
    monkeypatch.setenv("MINIFLUX_TOKEN", "test-token")
    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", lambda *a, **k: miniflux_payload)
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead", "--base-opml", str(base_xml)])

    if expected_exit is None:
        assert check_feeds.main() is None
    else:
        with pytest.raises(SystemExit) as exc:
            check_feeds.main()
        assert exc.value.code == expected_exit
