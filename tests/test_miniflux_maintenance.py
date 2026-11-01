"""Exercise the maintenance plan without real credentials or network access."""

from __future__ import annotations

import httpx

from scripts import miniflux_maintenance as maintenance


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
    client, calls = _client(
        [repair.old for repair in maintenance.REPAIRS] + ["https://projectzero.google/feed.xml"]
    )
    assert maintenance.run(client, "https://mf.example/", "fake-token") == 0
    assert calls == []
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(maintenance.REPAIRS) + 1
    assert lines[-1] == "Summary (dry-run): repoint=8 delete=13 skip=0 failed=0"
    for repair, line in zip(maintenance.REPAIRS, lines[:-1], strict=True):
        assert line.startswith(f"{repair.action} {repair.old}")
        assert repair.reason in line
        if repair.new:
            assert f" -> {repair.new}" in line


def test_existing_project_zero_canonical_is_preserved(capsys) -> None:
    canonical = "https://projectzero.google/feed.xml"
    urls = [repair.old for repair in maintenance.REPAIRS] + [canonical]
    client, calls = _client(urls)
    assert maintenance.run(client, "https://mf.example", "fake-token") == 0
    assert calls == []
    report = capsys.readouterr().out
    assert "delete https://googleprojectzero.blogspot.com/feeds/posts/default?alt=rss" in report
    assert "delete https://googleprojectzero.blogspot.com/feeds/posts/default |" in report
    assert "Summary (dry-run): repoint=8 delete=13 skip=0 failed=0" in report


def test_apply_uses_ids_and_verified_replacements(capsys) -> None:
    urls = [repair.old for repair in maintenance.REPAIRS] + ["https://projectzero.google/feed.xml"]
    client, calls = _client(urls)
    assert maintenance.run(client, "https://mf.example", "fake-token", apply=True) == 0
    for i, repair in enumerate(maintenance.REPAIRS, start=1):
        method, path, body = calls[i - 1]
        assert path == f"/v1/feeds/{i}"
        assert method == ("PUT" if repair.action == "repoint" else "DELETE")
        if repair.new:
            assert body == f'{{"feed_url":"{repair.new}"}}'
        else:
            assert body is None
    assert "Summary (apply): repoint=8 delete=13 skip=0 failed=0" in capsys.readouterr().out
    assert len(calls) == len(maintenance.REPAIRS)
    assert all(path != f"/v1/feeds/{len(urls)}" for _, path, _ in calls)


def test_missing_or_colliding_target_prevents_all_writes(capsys) -> None:
    urls = [
        repair.old for repair in maintenance.REPAIRS if repair.old != maintenance.REPAIRS[0].old
    ]
    urls.extend(["https://projectzero.google/feed.xml", maintenance.REPAIRS[8].new or ""])
    client, calls = _client(urls)
    assert maintenance.run(client, "https://mf.example", "fake-token", apply=True) == 1
    assert calls == []  # refuse incomplete plan before doing irreversible deletions
    report = capsys.readouterr().out
    assert "missing from Miniflux" in report
    assert "replacement already subscribed" in report
    assert "Summary (apply): repoint=0 delete=0 skip=21 failed=0" in report


def test_api_failure_is_reported_and_fails_run(capsys) -> None:
    urls = [repair.old for repair in maintenance.REPAIRS] + ["https://projectzero.google/feed.xml"]
    client, calls = _client(urls, fail_on="/v1/feeds/1")
    assert maintenance.run(client, "https://mf.example", "fake-token", apply=True) == 1
    assert calls[0][0] == "DELETE"
    assert "API failure" in capsys.readouterr().out
