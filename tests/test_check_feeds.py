"""Tests for the feed health classifier and retry pass."""

from __future__ import annotations

import pytest
import requests

from scripts import check_feeds


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def close(self) -> None:
        pass


@pytest.mark.parametrize(
    ("status", "bucket"),
    [
        (200, "ok"),
        (301, "ok"),
        (404, "dead"),
        (403, "dead"),
        (500, "transient"),
        (503, "transient"),
        (429, "transient"),
        ("timeout", "transient"),
        ("ssl_error", "dead"),
        ("conn_error", "dead"),
    ],
)
def test_classify(status: int | str, bucket: str) -> None:
    assert check_feeds.classify(status) == bucket


def test_check_url_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_feeds.requests, "head", lambda *a, **k: _Resp(200))
    assert check_feeds.check_url("https://example.com/feed") == ("https://example.com/feed", 200)


def test_check_url_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_timeout(*_a: object, **_k: object) -> None:
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(check_feeds.requests, "head", raise_timeout)
    assert check_feeds.check_url("https://example.com/feed") == (
        "https://example.com/feed",
        "timeout",
    )


def test_check_url_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_ssl(*_a: object, **_k: object) -> None:
        raise requests.exceptions.SSLError()

    monkeypatch.setattr(check_feeds.requests, "head", raise_ssl)
    assert check_feeds.check_url("https://example.com/feed") == (
        "https://example.com/feed",
        "ssl_error",
    )


def test_check_url_conn_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_conn(*_a: object, **_k: object) -> None:
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(check_feeds.requests, "head", raise_conn)
    assert check_feeds.check_url("https://example.com/feed") == (
        "https://example.com/feed",
        "conn_error",
    )


def test_check_url_head_403_falls_back_to_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_feeds.requests, "head", lambda *a, **k: _Resp(403))
    monkeypatch.setattr(check_feeds.requests, "get", lambda *a, **k: _Resp(200))
    assert check_feeds.check_url("https://example.com/feed") == (
        "https://example.com/feed",
        200,
    )


def test_classify_batch_promotes_retry_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A URL that returns 403 then 200 on retry should land in 'ok', not 'dead'."""
    url = "https://example.com/flaky"
    calls: list[int] = []

    def flaky_head(*_a: object, **_k: object) -> _Resp:
        calls.append(1)
        return _Resp(403 if len(calls) == 1 else 200)

    def flaky_get(*_a: object, **_k: object) -> _Resp:
        return _Resp(403 if len(calls) == 1 else 200)

    monkeypatch.setattr(check_feeds.requests, "head", flaky_head)
    monkeypatch.setattr(check_feeds.requests, "get", flaky_get)

    classified = check_feeds.classify_batch([url], pause_seconds=0)
    assert classified[url][0] == "ok"


def test_classify_batch_keeps_persistent_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://example.com/gone"
    monkeypatch.setattr(check_feeds.requests, "head", lambda *a, **k: _Resp(404))
    classified = check_feeds.classify_batch([url], pause_seconds=0)
    assert classified[url][0] == "dead"


def test_fail_on_dead_exit_code(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys) -> None:
    """CLI --fail-on-dead exits non-zero when any URL stays dead after retry."""
    opml = tmp_path / "feeds.xml"
    opml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opml version="1.0"><head><title>t</title></head><body>'
        '<outline text="F"><outline type="rss" text="broken" '
        'xmlUrl="https://example.com/gone" htmlUrl="https://example.com/"></outline>'
        "</outline></body></opml>",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_feeds, "FEEDS_XML", opml)
    monkeypatch.setattr(check_feeds.requests, "head", lambda *a, **k: _Resp(404))
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])

    with pytest.raises(SystemExit) as exc:
        check_feeds.main()
    assert exc.value.code == 1


def test_fail_on_dead_passes_when_all_ok(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    opml = tmp_path / "feeds.xml"
    opml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opml version="1.0"><head><title>t</title></head><body>'
        '<outline text="F"><outline type="rss" text="live" '
        'xmlUrl="https://example.com/live" htmlUrl="https://example.com/"></outline>'
        "</outline></body></opml>",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_feeds, "FEEDS_XML", opml)
    monkeypatch.setattr(check_feeds.requests, "head", lambda *a, **k: _Resp(200))
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])

    # Returns None on success (no SystemExit raised)
    assert check_feeds.main() is None
