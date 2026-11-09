"""Live feed-probe behavior from synthetic HTTP responses."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import httpx
import pytest

from scripts import check_feeds

RSS = (
    b"<rss version='2.0'><channel><title>News</title>"
    b"<item><title>A</title></item></channel></rss>"
)
ATOM = (
    b"<feed xmlns='http://www.w3.org/2005/Atom'><title>News</title>"
    b"<entry><title>A</title></entry></feed>"
)
URL = "https://example.test/feed"


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=check_feeds.TIMEOUT)


@pytest.mark.parametrize(("status", "body", "expected"), [
    (200, RSS, "healthy"),
    (200, ATOM, "healthy"),
    (200, b"<rss><channel><title>CAPTCHA security research</title></channel></rss>", "healthy"),
    (200, b"<root><title>unrelated XML</title></root>", "invalid"),
    (200, b"<rss><channel>", "invalid"),
    (200, b"<html><body>Welcome</body></html>", "invalid"),
    (200, b"<html>Cloudflare ray id 123; CAPTCHA</html>", "blocked-to-this-client"),
    (404, b"", "gone"),
    (410, b"", "gone"),
    (403, b"", "blocked-to-this-client"),
    (429, b"", "unreachable"),
    (503, b"", "unreachable"),
    (401, b"", "unreachable"),
])
def test_live_classification(status: int, body: bytes, expected: str) -> None:
    with client(lambda request: httpx.Response(status, content=body)) as http:
        result = check_feeds.probe_feed(URL, http, sleep=lambda _: None)
    assert (result.verdict, result.status_code, result.final_url) == (expected, status, URL)
    assert result.attempts == (3 if status in {429, 503} else 1)


@pytest.mark.parametrize("error", [httpx.ConnectError, httpx.ReadTimeout])
def test_network_errors_retry_without_dead_verdict(error: type[httpx.RequestError]) -> None:
    calls = []
    def handler(request):
        calls.append(request)
        raise error("connection problem", request=request)
    with client(handler) as http:
        result = check_feeds.probe_feed(URL, http, sleep=lambda _: None)
    assert result.verdict == "unreachable" and result.status_code is None
    assert result.attempts == len(calls) == 3


def test_retry_backoff_and_recovery() -> None:
    calls = []
    delays = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429)
        if len(calls) == 2:
            return httpx.Response(502)
        return httpx.Response(200, content=RSS)
    with client(handler) as http:
        result = check_feeds.probe_feed(URL, http, sleep=delays.append)
    assert (result.verdict, result.attempts, delays) == ("healthy", 3, [0.3, 0.6])
    assert all("rss+xml" in request.headers["Accept"] and
               "infosec-opml" in request.headers["User-Agent"] for request in calls)


def test_redirect_chain_preserves_final_status_and_url() -> None:
    paths = []
    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/feed":
            return httpx.Response(301, headers={"Location": "/second"})
        if request.url.path == "/second":
            return httpx.Response(302, headers={"Location": "/final"})
        return httpx.Response(200, content=ATOM)
    with client(handler) as http:
        result = check_feeds.probe_feed(URL, http)
    assert (result.verdict, result.status_code, result.final_url, result.attempts) == (
        "healthy", 200, "https://example.test/final", 1)
    assert paths == ["/feed", "/second", "/final"]


def test_bounded_body_and_independent_failures() -> None:
    feeds = [check_feeds.FeedRow("bad", "not-a-url", "a"),
             check_feeds.FeedRow("oversize", URL, "b")]
    with client(
        lambda request: httpx.Response(200, content=RSS + b"x" * check_feeds.MAX_BODY)
    ) as http:
        result = check_feeds.probe_feeds(feeds, http, workers=2)
    assert result["not-a-url"].verdict == "invalid"
    assert result[URL].verdict == "unreachable"
    assert result[URL].detail == "body exceeds 8 MiB cap"


def test_worker_limit_and_duplicate_url_only_probed_once() -> None:
    active = 0
    peak = 0
    count = 0
    lock = threading.Lock()
    def handler(request):
        nonlocal active, peak, count
        with lock:
            active += 1
            count += 1
            peak = max(active, peak)
        time.sleep(0.012)
        with lock:
            active -= 1
        return httpx.Response(200, content=RSS)
    feeds = [check_feeds.FeedRow(str(n), f"https://example.test/{n}", "a") for n in range(16)]
    feeds.append(feeds[0])
    with client(handler) as http:
        results = check_feeds.probe_feeds(feeds, http, workers=3)
    assert len(results) == count == 16
    assert 1 < peak <= 3
    assert all(result.verdict == "healthy" for result in results.values())


def test_main_uses_probe_not_sticky_miniflux_and_only_live_gone_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "feeds.xml"
    source.write_text("<opml><body><outline text='a'><outline text='good' type='rss' "
                      "xmlUrl='https://example.test/feed'/></outline></body></opml>")
    base = tmp_path / "base.xml"
    base.write_text("<opml><body/></opml>")
    monkeypatch.setattr(check_feeds, "FEEDS_XML", source)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.test")
    monkeypatch.setenv("MINIFLUX_TOKEN", "secret")
    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", lambda *args: {
        URL: check_feeds.MinifluxStatus(True, 99, "404 from Miniflux")})
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead", "--base-opml", str(base),
                                    "--min-error-count", "2"])
    real_probe = check_feeds.probe_feeds
    with client(lambda request: httpx.Response(200, content=RSS)) as http:
        monkeypatch.setattr(check_feeds, "probe_feeds", lambda feeds: real_probe(feeds, http))
        assert check_feeds.main() is None
    assert "1 healthy, 0 gone" in capsys.readouterr().out
    with client(lambda request: httpx.Response(410)) as http:
        monkeypatch.setattr(check_feeds, "probe_feeds", lambda feeds: real_probe(feeds, http))
        with pytest.raises(SystemExit) as exc:
            check_feeds.main()
    assert exc.value.code == 1
    assert "New in PR base comparison" in capsys.readouterr().out


def test_miniflux_unavailable_does_not_skip_probes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    source = tmp_path / "feeds.xml"
    source.write_text("<opml><body><outline text='a'><outline type='rss' "
                      "xmlUrl='https://example.test/feed'/></outline></body></opml>")
    monkeypatch.setattr(check_feeds, "FEEDS_XML", source)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.test")
    monkeypatch.setenv("MINIFLUX_TOKEN", "secret")
    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", lambda *args: (_ for _ in ()).throw(
        httpx.ConnectError("offline")))
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])
    real_probe = check_feeds.probe_feeds
    with client(lambda request: httpx.Response(200, content=RSS)) as http:
        monkeypatch.setattr(check_feeds, "probe_feeds", lambda feeds: real_probe(feeds, http))
        assert check_feeds.main() is None


def test_min_error_count_filters_history_without_changing_live_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "feeds.xml"
    source.write_text(
        "<opml><body><outline text='a'><outline type='rss' "
        "xmlUrl='https://example.test/feed'/></outline></body></opml>"
    )
    monkeypatch.setattr(check_feeds, "FEEDS_XML", source)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.test")
    monkeypatch.setenv("MINIFLUX_TOKEN", "secret")
    monkeypatch.setattr(check_feeds, "fetch_miniflux_feeds", lambda *args: {
        URL: check_feeds.MinifluxStatus(False, 2, "old failure"),
    })
    real_probe = check_feeds.probe_feeds
    with client(lambda request: httpx.Response(200, content=b"<html>not feed</html>")) as http:
        monkeypatch.setattr(check_feeds, "probe_feeds", lambda feeds: real_probe(feeds, http))
        monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])
        assert check_feeds.main() is None
        assert "Miniflux history:" not in capsys.readouterr().out
        monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead", "--min-error-count", "2"])
        assert check_feeds.main() is None
        report = capsys.readouterr().out
        assert "Miniflux history: 2 errors" in report
        assert "0 gone" in report
