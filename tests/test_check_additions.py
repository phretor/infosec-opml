"""Tests for the additions-only contributor PR gate."""

from __future__ import annotations

from dataclasses import replace

from scripts.check_additions import check_additions
from scripts.miniflux_sync import Feed

THREAT = "07 🕵️ Threat Intel, Malware & Detection"
NEWS = "14 🗞️ Security News & Commentary"
A = Feed(name="A", folder=THREAT, xml_url="https://a.example/feed", html_url="https://a.example/")
B = Feed(name="B", folder=NEWS, xml_url="https://b.example/feed", html_url="https://b.example/")
NEW = Feed(name="N", folder=NEWS, xml_url="https://n.example/feed", html_url="https://n.example/")


def _rules(base: list[Feed], head: list[Feed]) -> list[str]:
    return [e.rule for e in check_additions(base, head)]


def test_additions_to_existing_folders_pass_in_any_position() -> None:
    assert _rules([A, B], [NEW, B, A]) == []


def test_unchanged_list_passes() -> None:
    assert _rules([A, B], [A, B]) == []


def test_removing_a_feed_fails() -> None:
    assert _rules([A, B], [A, NEW]) == ["removed-feed"]


def test_moving_a_feed_fails() -> None:
    assert _rules([A, B], [replace(A, folder=NEWS), B]) == ["changed-feed"]


def test_editing_feed_metadata_fails() -> None:
    errors = check_additions([A, B], [replace(A, name="A2", html_url="https://x.example/"), B])
    assert [e.rule for e in errors] == ["changed-feed"]
    assert "name" in errors[0].message
    assert "html_url" in errors[0].message


def test_changing_a_feed_url_is_a_removal() -> None:
    assert _rules([A, B], [replace(A, xml_url="https://a.example/rss"), B]) == ["removed-feed"]


def test_adding_a_feed_in_a_new_folder_fails() -> None:
    assert _rules([A, B], [A, B, replace(NEW, folder="99 🆕 Brand New")]) == ["new-folder"]
