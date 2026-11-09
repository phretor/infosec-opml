"""Exercise the maintenance plan without real credentials or network access."""

from __future__ import annotations

import httpx
import pytest

from scripts import miniflux_maintenance as maintenance

R0RT1Z2 = "https://blog.r0rt1z2.com/rss.xml"
FIRMWARE_SECURITY = "https://firmwaresecurity.com/feed/"
UNRELATED = "https://example.org/feed.xml"


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
    client, calls = _client([UNRELATED, R0RT1Z2, FIRMWARE_SECURITY])
    assert maintenance.run(client, "https://mf.example/", "fake-token") == 0
    assert calls == []
    assert capsys.readouterr().out.splitlines() == [
        f"delete {R0RT1Z2} | live 404; no replacement found",
        f"delete {FIRMWARE_SECURITY} | domain parked for sale; no feed",
        "Summary (dry-run): repoint=0 delete=2 skip=0 failed=0",
    ]


def test_apply_deletes_each_target_id_exactly_once(capsys) -> None:
    client, calls = _client([UNRELATED, R0RT1Z2, UNRELATED, FIRMWARE_SECURITY])
    assert maintenance.run(client, "https://mf.example", "fake-token", apply=True) == 0
    assert calls == [
        ("DELETE", "/v1/feeds/2", None),
        ("DELETE", "/v1/feeds/4", None),
    ]
    assert "Summary (apply): repoint=0 delete=2 skip=0 failed=0" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("urls", "reason"),
    [
        ([R0RT1Z2, UNRELATED], "missing from Miniflux"),
        ([R0RT1Z2, R0RT1Z2, FIRMWARE_SECURITY], "ambiguous URL"),
    ],
)
def test_missing_or_ambiguous_target_prevents_all_writes(
    capsys, urls: list[str], reason: str
) -> None:
    client, calls = _client(urls)
    assert maintenance.run(client, "https://mf.example", "fake-token", apply=True) == 1
    assert calls == []
    report = capsys.readouterr().out
    assert reason in report
    assert "plan incomplete; no mutations" in report
    assert "Summary (apply): repoint=0 delete=0 skip=2 failed=0" in report


def test_api_failure_is_reported_and_fails_run(capsys) -> None:
    client, calls = _client([R0RT1Z2, FIRMWARE_SECURITY], fail_on="/v1/feeds/1")
    assert maintenance.run(client, "https://mf.example", "fake-token", apply=True) == 1
    assert calls == [
        ("DELETE", "/v1/feeds/1", None),
        ("DELETE", "/v1/feeds/2", None),
    ]
    report = capsys.readouterr().out
    assert f"skip {R0RT1Z2} | API failure:" in report
    assert "Summary (apply): repoint=0 delete=1 skip=0 failed=1" in report
