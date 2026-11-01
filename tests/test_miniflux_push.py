"""Tests for the additive repo -> Miniflux push. Miniflux is an in-memory httpx mock."""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import quoteattr

import httpx
import pytest

from scripts import miniflux_push
from scripts.miniflux_push import MinifluxApi, plan_additions, push_additions
from scripts.miniflux_sync import Feed

THREAT = "07 🕵️ Threat Intel, Malware & Detection"
NEWS = "14 🗞️ Security News & Commentary"
READ_ONLY_OR_CREATE = {("GET", "/v1/categories"), ("GET", "/v1/feeds"), ("POST", "/v1/feeds")}


def _feed(url: str, folder: str = THREAT, name: str = "Example") -> Feed:
    return Feed(name=name, folder=folder, xml_url=url, html_url="https://example.com/", title=name)


class FakeMiniflux:
    """Stateful Miniflux double: answers the API and records every request."""

    def __init__(self, categories: dict[str, int], feed_urls: list[str]) -> None:
        self.categories = dict(categories)
        self.feeds = [{"id": i + 1, "feed_url": u} for i, u in enumerate(feed_urls)]
        self.reject: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []
        self.created: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Auth-Token") == "test-token"
        route = (request.method, request.url.path)
        self.calls.append(route)
        if route == ("GET", "/v1/categories"):
            return httpx.Response(
                200, json=[{"id": i, "title": t} for t, i in self.categories.items()]
            )
        if route == ("GET", "/v1/feeds"):
            return httpx.Response(200, json=self.feeds)
        if route == ("POST", "/v1/feeds"):
            body = json.loads(request.content)
            url = body["feed_url"]
            if url in self.reject:
                return httpx.Response(400, json={"error_message": self.reject[url]})
            if any(f["feed_url"] == url for f in self.feeds):
                return httpx.Response(400, json={"error_message": "This feed already exists."})
            feed_id = len(self.feeds) + 1
            self.feeds.append({"id": feed_id, "feed_url": url})
            self.created.append(body)
            return httpx.Response(201, json={"feed_id": feed_id})
        return httpx.Response(404, json={"error_message": "unexpected route"})

    def api(self) -> MinifluxApi:
        client = httpx.Client(transport=httpx.MockTransport(self.handler))
        return MinifluxApi(client, "https://mf.example/", "test-token")


@pytest.fixture
def miniflux() -> FakeMiniflux:
    return FakeMiniflux({THREAT: 7, NEWS: 14}, ["https://old.example/feed"])


def test_plan_counts_only_new_urls_not_removals_or_moves() -> None:
    before = [_feed("https://a.example/feed"), _feed("https://b.example/feed")]
    after = [
        _feed("https://b.example/feed", folder=NEWS, name="Renamed and moved"),
        _feed("https://c.example/feed"),
        _feed("https://c.example/feed", folder=NEWS),
    ]
    assert plan_additions(before, after) == [_feed("https://c.example/feed")]


def test_creates_new_feed_in_matching_category(miniflux: FakeMiniflux) -> None:
    results = push_additions(miniflux.api(), [_feed("https://new.example/feed", folder=NEWS)])

    assert [r.outcome for r in results] == ["created"]
    assert miniflux.created == [{"feed_url": "https://new.example/feed", "category_id": 14}]


def test_never_calls_anything_but_list_and_create(miniflux: FakeMiniflux) -> None:
    miniflux.reject["https://bad.example/feed"] = "unable to parse feed"
    additions = [
        _feed("https://new.example/feed"),
        _feed("https://old.example/feed/"),
        _feed("https://bad.example/feed"),
        _feed("https://orphan.example/feed", folder="99 🆕 Brand New Folder"),
    ]

    push_additions(miniflux.api(), additions)

    assert set(miniflux.calls) <= READ_ONLY_OR_CREATE
    assert miniflux.categories == {THREAT: 7, NEWS: 14}
    assert [f["feed_url"] for f in miniflux.feeds] == [
        "https://old.example/feed",
        "https://new.example/feed",
    ]


def test_second_run_is_a_no_op(miniflux: FakeMiniflux) -> None:
    additions = [_feed("https://new.example/feed"), _feed("https://other.example/rss", NEWS)]
    first = push_additions(miniflux.api(), additions)
    calls_after_first = len(miniflux.calls)

    second = push_additions(miniflux.api(), additions)

    assert [r.outcome for r in first] == ["created", "created"]
    assert [r.outcome for r in second] == ["present", "present"]
    assert ("POST", "/v1/feeds") not in miniflux.calls[calls_after_first:]
    assert len(miniflux.feeds) == 3


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("https://old.example/feed", id="exact"),
        pytest.param("https://old.example/feed/", id="trailing-slash"),
        pytest.param("http://OLD.example/feed", id="scheme-and-host-case"),
    ],
)
def test_existing_subscription_is_not_duplicated(miniflux: FakeMiniflux, url: str) -> None:
    results = push_additions(miniflux.api(), [_feed(url)])

    assert [r.outcome for r in results] == ["present"]
    assert ("POST", "/v1/feeds") not in miniflux.calls


def test_unknown_folder_fails_without_creating_a_category(miniflux: FakeMiniflux) -> None:
    results = push_additions(
        miniflux.api(), [_feed("https://new.example/feed", folder="99 🆕 Brand New Folder")]
    )

    assert [r.outcome for r in results] == ["failed"]
    assert "no Miniflux category" in results[0].detail
    assert ("POST", "/v1/feeds") not in miniflux.calls
    assert ("POST", "/v1/categories") not in miniflux.calls


@pytest.mark.parametrize(
    "url",
    [
        "ftp://files.example/feed.xml",
        "file:///etc/passwd",
        "http://localhost:8080/v1/feeds",
        "http://127.0.0.1/feed",
        "http://[::1]/feed",
        "http://169.254.169.254/latest/meta-data/",
        "http://miniflux.internal/feed",
        "http://printer.local/feed",
        "http://intranet/feed",
    ],
)
def test_non_public_urls_are_never_sent_to_miniflux(miniflux: FakeMiniflux, url: str) -> None:
    results = push_additions(miniflux.api(), [_feed(url)])

    assert [r.outcome for r in results] == ["failed"]
    assert miniflux.calls == []


def test_one_rejected_feed_does_not_block_the_others(miniflux: FakeMiniflux) -> None:
    miniflux.reject["https://bad.example/feed"] = "unable to parse feed"
    additions = [_feed("https://bad.example/feed"), _feed("https://good.example/feed")]

    results = push_additions(miniflux.api(), additions)

    assert [r.outcome for r in results] == ["failed", "created"]
    assert "unable to parse feed" in results[0].detail


def test_dry_run_creates_nothing(miniflux: FakeMiniflux) -> None:
    results = push_additions(miniflux.api(), [_feed("https://new.example/feed")], dry_run=True)

    assert [r.outcome for r in results] == ["would-create"]
    assert ("POST", "/v1/feeds") not in miniflux.calls


def test_feed_deleted_in_miniflux_is_not_resurrected(miniflux: FakeMiniflux) -> None:
    """A feed still in the repo but already deleted in Miniflux is outside the merged diff."""
    deleted = _feed("https://deleted.example/feed")
    before = [deleted]
    after = [deleted, _feed("https://new.example/feed")]

    push_additions(miniflux.api(), plan_additions(before, after))

    assert [c["feed_url"] for c in miniflux.created] == ["https://new.example/feed"]


def _opml(tmp_path: Path, name: str, urls: list[str]) -> Path:
    leaves = "".join(
        f'<outline text="F" title="F" type="rss" xmlUrl="{u}" htmlUrl="{u}"></outline>'
        for u in urls
    )
    path = tmp_path / name
    path.write_text(
        f'<opml version="1.0"><head/><body><outline text={quoteattr(THREAT)}>{leaves}</outline>'
        "</body></opml>",
        encoding="utf-8",
    )
    return path


def test_main_without_additions_needs_no_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_TOKEN", raising=False)
    before = _opml(tmp_path, "before.xml", ["https://a.example/feed", "https://b.example/feed"])
    after = _opml(tmp_path, "after.xml", ["https://a.example/feed"])

    assert miniflux_push.main(["--before", str(before), "--after", str(after)]) == 0
    assert "No feed additions" in capsys.readouterr().out


def test_main_with_additions_requires_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_TOKEN", raising=False)
    before = _opml(tmp_path, "before.xml", ["https://a.example/feed"])
    after = _opml(tmp_path, "after.xml", ["https://a.example/feed", "https://b.example/feed"])

    assert miniflux_push.main(["--before", str(before), "--after", str(after)]) == 2
