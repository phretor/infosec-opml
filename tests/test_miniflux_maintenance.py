"""Exercise the maintenance plan without real credentials or network access."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

from scripts import miniflux_maintenance as maintenance
from scripts.miniflux_maintenance import Repair
from scripts.miniflux_push import url_key

OLD = "https://example.org/old.xml"
NEW = "https://example.org/new.xml"
OTHER = "https://example.org/other.xml"
PLAN = (
    Repair("repoint", OLD, "301 to https://example.org/new.xml; target 200 RSS", NEW),
    Repair("delete", OTHER, "404; no replacement found"),
)
FEEDS_XML = Path(__file__).resolve().parent.parent / "feeds.xml"
DROPPED = {
    "https://blog.rapid7.com/rss/",
    "https://www.rcesecurity.com/feed",
    "https://adam.shostack.org/blog/feed/",
    "https://www.secjuice.com/rss/",
    "https://dysruptionhub.com/feed/",
    "https://www.datacenterdynamics.com/rss",
}


def _client(
    urls: list[str], *, fail_on: str | None = None
) -> tuple[httpx.Client, list[tuple[str, str, str | None]]]:
    calls: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Auth-Token"] == "fake-token"
        if request.method == "GET":
            return httpx.Response(
                200, json=[{"id": i + 1, "feed_url": url} for i, url in enumerate(urls)]
            )
        new_url = request.read().decode() if request.method == "PUT" else None
        calls.append((request.method, request.url.path, new_url))
        if request.url.path == fail_on:
            return httpx.Response(500)
        return httpx.Response(200 if request.method == "PUT" else 204)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_dry_run_lists_exact_plan_without_mutations(capsys) -> None:
    client, calls = _client([repair.old for repair in maintenance.REPAIRS])
    assert maintenance.run(client, "https://mf.example/", "fake-token") == 0
    assert calls == []
    lines = capsys.readouterr().out.splitlines()
    repoints = sum(repair.action == "repoint" for repair in maintenance.REPAIRS)
    deletes = sum(repair.action == "delete" for repair in maintenance.REPAIRS)
    assert lines[-1] == f"Summary (dry-run): repoint={repoints} delete={deletes} skip=0 failed=0"
    assert len(lines) == len(maintenance.REPAIRS) + 1
    for repair, line in zip(maintenance.REPAIRS, lines[:-1], strict=True):
        assert line.startswith(f"{repair.action} {repair.old}")
        assert repair.reason in line
        if repair.new:
            assert f" -> {repair.new}" in line


def test_plan_matches_feeds_xml_and_drops_unconfirmed_leads() -> None:
    urls = {
        url for el in ET.parse(FEEDS_XML).iter("outline") if (url := el.get("xmlUrl")) is not None
    }
    keys = {url_key(url) for url in urls}
    olds = [repair.old for repair in maintenance.REPAIRS]
    news = [repair.new for repair in maintenance.REPAIRS if repair.new is not None]
    assert len(olds) == len(set(olds))
    assert len(news) == len(set(news))
    assert set(news).isdisjoint(olds)
    assert DROPPED.isdisjoint(olds)
    by_old = {repair.old: repair for repair in maintenance.REPAIRS}
    zdnet_keep = by_old["https://www.zdnet.com/topic/security/rss.xml"]
    zdnet_drop = by_old["https://www.zdnet.com/blog/security/rss.xml"]
    assert zdnet_keep.action == "repoint"
    assert zdnet_keep.new == "https://www.zdnet.com/rss/security/"
    assert zdnet_drop.action == "delete" and zdnet_drop.new is None
    assert by_old["https://blog.fox-it.com/feed/"].action == "delete"
    assert by_old["https://blog.convisoappsec.com/feed/"].action == "delete"
    carnal = by_old["https://carnal0wnage.blogspot.com/feeds/posts/default"]
    assert carnal.action == "repoint"
    assert carnal.new == "https://blog.carnal0wnage.com/feeds/posts/default"
    assert carnal.reason == (
        "301 to http://blog.carnal0wnage.com/feeds/posts/default; "
        "the https form serves application/atom+xml 200."
    )
    techmeme = by_old["https://www.techmeme.com/index.xml"]
    assert techmeme.action == "repoint"
    assert techmeme.new == "https://www.techmeme.com/feed.xml"
    assert techmeme.reason == (
        "301 to http://www.techmeme.com/feed.xml; the https form serves valid RSS 200."
    )
    for repair in maintenance.REPAIRS:
        assert repair.old in urls
        assert repair.reason
        if repair.action == "repoint":
            assert repair.new is not None
            assert repair.new not in urls
            assert url_key(repair.new) not in keys
            assert "200" in repair.reason
        else:
            assert repair.action == "delete"
            assert repair.new is None


def test_apply_repoints_and_deletes_by_id(monkeypatch, capsys) -> None:
    monkeypatch.setattr(maintenance, "REPAIRS", PLAN)
    client, calls = _client(["https://unrelated.example/feed.xml", OLD, OTHER])
    assert maintenance.run(client, "https://mf.example", "fake-token", apply=True) == 0
    assert calls == [
        ("PUT", "/v1/feeds/2", '{"feed_url":"https://example.org/new.xml"}'),
        ("DELETE", "/v1/feeds/3", None),
    ]
    report = capsys.readouterr().out
    assert f"repoint {OLD} -> {NEW}" in report
    assert f"delete {OTHER}" in report
    assert "Summary (apply): repoint=1 delete=1 skip=0 failed=0" in report


@pytest.mark.parametrize("apply", [False, True])
@pytest.mark.parametrize(
    ("urls", "reason"),
    [
        ([OTHER], "missing from Miniflux"),
        ([OLD, OLD, OTHER], "ambiguous URL"),
        ([OLD, OTHER, NEW], "replacement already subscribed"),
    ],
)
def test_one_invalid_entry_blocks_every_write(
    monkeypatch, capsys, apply: bool, urls: list[str], reason: str
) -> None:
    monkeypatch.setattr(maintenance, "REPAIRS", PLAN)
    client, calls = _client(urls)
    assert maintenance.run(client, "https://mf.example", "fake-token", apply=apply) == 1
    assert calls == []
    report = capsys.readouterr().out
    mode = "apply" if apply else "dry-run"
    assert f"blocking: {reason}" in report
    assert "plan incomplete; no mutations" in report
    assert "Apply will mutate nothing." in report
    assert f"Summary ({mode}): repoint=0 delete=0 skip=2 failed=0" in report
    assert not any(line.startswith(("repoint ", "delete ")) for line in report.splitlines())


def test_api_failure_is_reported_and_fails_run(monkeypatch, capsys) -> None:
    monkeypatch.setattr(maintenance, "REPAIRS", PLAN)
    client, calls = _client([OLD, OTHER], fail_on="/v1/feeds/1")
    assert maintenance.run(client, "https://mf.example", "fake-token", apply=True) == 1
    assert calls == [
        ("PUT", "/v1/feeds/1", '{"feed_url":"https://example.org/new.xml"}'),
        ("DELETE", "/v1/feeds/2", None),
    ]
    report = capsys.readouterr().out
    assert f"skip {OLD} -> {NEW} | API failure:" in report
    assert f"delete {OTHER}" in report
    assert "Summary (apply): repoint=0 delete=1 skip=0 failed=1" in report
