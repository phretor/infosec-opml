"""Live feed-probe behavior from synthetic HTTP responses."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import brotli
import httpx
import pytest

from scripts import check_feeds

RSS = (
    b"<rss version='2.0'><channel><title>News</title><item><title>A</title></item></channel></rss>"
)
ATOM = (
    b"<feed xmlns='http://www.w3.org/2005/Atom'><title>News</title>"
    b"<entry><title>A</title></entry></feed>"
)
URL = "https://example.test/feed"


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=check_feeds.TIMEOUT)


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
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
    ],
)
def test_live_classification(status: int, body: bytes, expected: str) -> None:
    with client(lambda request: httpx.Response(status, content=body)) as http:
        result = check_feeds.probe_feed(URL, http, sleep=lambda _: None)
    assert (result.verdict, result.status_code, result.final_url) == (expected, status, URL)
    assert result.attempts == (3 if status in {429, 503} else 1)


def test_brotli_feed_is_decompressed_before_xml_validation() -> None:
    with client(
        lambda request: httpx.Response(
            200,
            content=brotli.compress(RSS),
            headers={"Content-Encoding": "br", "Content-Type": "application/rss+xml"},
        )
    ) as http:
        result = check_feeds.probe_feed(URL, http)
    assert result.verdict == "healthy"


def test_invalid_response_preserves_diagnostic_headers_and_sample() -> None:
    body = b"<html><body>not a feed</body></html>"
    with client(
        lambda request: httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    ) as http:
        result = check_feeds.probe_feed(URL, http)
    assert result.verdict == "invalid" and result.detail == "HTML document"
    assert result.content_type == "text/html; charset=utf-8"
    assert result.charset == "utf-8" and result.sample == repr(body)


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
    assert all(
        "rss+xml" in request.headers["Accept"] and "infosec-opml" in request.headers["User-Agent"]
        for request in calls
    )


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
        "healthy",
        200,
        "https://example.test/final",
        1,
    )
    assert paths == ["/feed", "/second", "/final"]


def test_bounded_body_and_independent_failures() -> None:
    feeds = [
        check_feeds.FeedRow("bad", "not-a-url", "a"),
        check_feeds.FeedRow("oversize", URL, "b"),
    ]
    with client(
        lambda request: httpx.Response(200, content=RSS + b"x" * check_feeds.MAX_BODY)
    ) as http:
        result = check_feeds.probe_feeds(feeds, http, workers=2)
    assert result["not-a-url"].verdict == "invalid"
    assert result[URL].verdict == "unreachable"
    assert result[URL].detail == "body exceeds 16 MiB cap"


def test_large_valid_feed_below_sixteen_mib_is_healthy() -> None:
    body = (
        b"<rss><channel><title>News</title><item><description>"
        + (b"X" * (9 * 1024 * 1024))
        + b"</description></item></channel></rss>"
    )
    with client(lambda request: httpx.Response(200, content=body)) as http:
        result = check_feeds.probe_feed(URL, http)
    assert result.verdict == "healthy"


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
    source.write_text(
        "<opml><body><outline text='a'><outline text='good' type='rss' "
        "xmlUrl='https://example.test/feed'/></outline></body></opml>"
    )
    base = tmp_path / "base.xml"
    base.write_text("<opml><body/></opml>")
    monkeypatch.setattr(check_feeds, "FEEDS_XML", source)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.test")
    monkeypatch.setenv("MINIFLUX_TOKEN", "secret")
    monkeypatch.setattr(
        check_feeds,
        "refresh_miniflux_feeds",
        lambda *args: ({}, {}, {URL: check_feeds.MinifluxStatus(True, 99, "404 from Miniflux")}),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["check_feeds", "--fail-on-dead", "--base-opml", str(base), "--min-error-count", "2"],
    )
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "feeds.xml"
    source.write_text(
        "<opml><body><outline text='a'><outline type='rss' "
        "xmlUrl='https://example.test/feed'/></outline></body></opml>"
    )
    monkeypatch.setattr(check_feeds, "FEEDS_XML", source)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.test")
    monkeypatch.setenv("MINIFLUX_TOKEN", "secret")
    monkeypatch.setattr(
        check_feeds,
        "refresh_miniflux_feeds",
        lambda *args: (_ for _ in ()).throw(httpx.ConnectError("offline")),
    )
    monkeypatch.setattr("sys.argv", ["check_feeds", "--fail-on-dead"])
    real_probe = check_feeds.probe_feeds
    with client(lambda request: httpx.Response(200, content=RSS)) as http:
        monkeypatch.setattr(check_feeds, "probe_feeds", lambda feeds: real_probe(feeds, http))
        assert check_feeds.main() is None


def test_min_error_count_filters_history_without_changing_live_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "feeds.xml"
    source.write_text(
        "<opml><body><outline text='a'><outline type='rss' "
        "xmlUrl='https://example.test/feed'/></outline></body></opml>"
    )
    monkeypatch.setattr(check_feeds, "FEEDS_XML", source)
    monkeypatch.setenv("MINIFLUX_URL", "https://mf.test")
    monkeypatch.setenv("MINIFLUX_TOKEN", "secret")
    monkeypatch.setattr(
        check_feeds,
        "refresh_miniflux_feeds",
        lambda *args: ({}, {}, {URL: check_feeds.MinifluxStatus(False, 2, "old failure")}),
    )
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


def test_ci_style_invocation_never_fails_on_feed_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "feeds.xml"
    source.write_text(
        "<opml><body><outline text='a'><outline type='rss' "
        "xmlUrl='https://example.test/feed'/></outline></body></opml>"
    )
    monkeypatch.setattr(check_feeds, "FEEDS_XML", source)
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["check_feeds"])
    real_probe = check_feeds.probe_feeds
    with client(lambda request: httpx.Response(404)) as http:
        monkeypatch.setattr(check_feeds, "probe_feeds", lambda feeds: real_probe(feeds, http))
        assert check_feeds.main() is None
    report = capsys.readouterr()
    assert "1 gone" in report.out
    assert "no authoritative verdict" in report.out


def test_miniflux_refresh_replaces_sticky_error_with_fresh_cluster_result() -> None:
    calls: list[tuple[str, str]] = []
    reads = 0
    feed = check_feeds.FeedRow("Feed", URL, "a")
    other = check_feeds.FeedRow("Other", "https://example.test/other", "a")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal reads
        calls.append((request.method, request.url.path))
        assert request.headers["X-Auth-Token"] == "token"
        if request.method == "PUT":
            assert request.url.path == "/v1/feeds/42/refresh"
            return httpx.Response(204)
        reads += 1
        return httpx.Response(
            200,
            json=[
                {
                    "id": 42,
                    "feed_url": URL,
                    "checked_at": f"check-{reads}",
                    "parsing_error_count": 9 if reads == 1 else 0,
                    "parsing_error_message": "HTTP 404" if reads == 1 else "",
                },
                {
                    "id": 43,
                    "feed_url": other.xml_url,
                    "checked_at": "old",
                    "parsing_error_count": 0,
                    "parsing_error_message": "",
                },
            ],
        )

    with client(handler) as http:
        fresh, failures, before = check_feeds.refresh_miniflux_feeds(
            [feed, other],
            {
                URL: check_feeds.Probe("blocked-to-this-client", 403, URL),
                other.xml_url: check_feeds.Probe("healthy", 200, other.xml_url),
            },
            "https://mf.test",
            "token",
            client=http,
            sleep=lambda _: None,
        )
    assert before[URL].parsing_error_count == 9
    assert failures == {}
    assert check_feeds.classify_fresh(fresh[URL]) == "healthy"
    assert other.xml_url not in fresh
    assert calls == [
        ("GET", "/v1/feeds"),
        ("PUT", "/v1/feeds/42/refresh"),
        ("GET", "/v1/feeds"),
    ]


def test_refresh_failure_never_promotes_stale_status_to_authority() -> None:
    feed = check_feeds.FeedRow("Feed", URL, "a")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(503)
        return httpx.Response(
            200,
            json=[
                {
                    "id": 42,
                    "feed_url": URL,
                    "checked_at": "unchanged",
                    "parsing_error_count": 7,
                    "parsing_error_message": "HTTP 404",
                }
            ],
        )

    with client(handler) as http:
        fresh, failures, _ = check_feeds.refresh_miniflux_feeds(
            [feed],
            {URL: check_feeds.Probe("gone", 404, URL)},
            "https://mf.test",
            "token",
            client=http,
            sleep=lambda _: None,
        )
    assert fresh == {}
    assert URL in failures


@pytest.mark.parametrize(
    ("count", "message", "expected"),
    [
        (0, "old HTTP 404", "healthy"),
        (1, "unexpected HTTP status code: 404", "gone"),
        (1, "unexpected HTTP status code: 410", "gone"),
        (1, "unexpected HTTP status code: 403", "blocked-to-this-client"),
        (1, "This website is too slow and the request timed out", "unreachable"),
        (1, "Unable to detect feed format", "invalid"),
    ],
)
def test_classify_only_refreshed_miniflux_state(
    count: int,
    message: str,
    expected: str,
) -> None:
    status = check_feeds.MinifluxStatus(False, count, message, id=42, checked_at="new")
    assert check_feeds.classify_fresh(status) == expected


def test_refresh_204_without_updated_timestamp_does_not_verify_feed() -> None:
    feed = check_feeds.FeedRow("Feed", URL, "a")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(204)
        return httpx.Response(
            200,
            json=[
                {
                    "id": 42,
                    "feed_url": URL,
                    "checked_at": "unchanged",
                    "parsing_error_count": 9,
                    "parsing_error_message": "old HTTP 404",
                }
            ],
        )

    with client(handler) as http:
        fresh, failures, _ = check_feeds.refresh_miniflux_feeds(
            [feed],
            {URL: check_feeds.Probe("gone", 404, URL)},
            "https://mf.test",
            "token",
            client=http,
            sleep=lambda _: None,
        )
    assert fresh == {}
    assert failures[URL] == "refresh not observable in subsequent Miniflux feed record"
