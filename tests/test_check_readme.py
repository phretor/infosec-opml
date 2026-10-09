"""Tests for scripts.check_readme."""

from pathlib import Path

from scripts.check_readme import check_readme

OPML_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<opml version="1.0"><head><title>t</title></head><body>\n'
)
OPML_FOOTER = "</body></opml>\n"


def _write_opml(tmp_path: Path, folders: dict[str, int]) -> Path:
    """Write a minimal OPML with the given {folder_name: feed_count} shape."""
    body = ""
    i = 0
    for folder, count in folders.items():
        body += f'<outline text="{folder}">\n'
        for _ in range(count):
            i += 1
            body += (
                f'<outline title="f{i}" text="f{i}" '
                f'xmlUrl="https://e{i}.example/feed" '
                f'htmlUrl="https://e{i}.example/" type="rss"/>\n'
            )
        body += "</outline>\n"
    p = tmp_path / "feeds.xml"
    p.write_text(OPML_HEADER + body + OPML_FOOTER, encoding="utf-8")
    return p


def _write_readme(
    tmp_path: Path,
    feed_count: int,
    folder_count: int,
    folders: list[str],
) -> Path:
    """Write a README with the sync-anchor sentences and a folder table."""
    rows = "\n".join(f"| {name} | desc |" for name in folders)
    text = (
        f"A collection of {feed_count} information security feeds.\n"
        f"They are organized into {folder_count} permanent, flat folders.\n"
        "\n"
        "| Folder | Description |\n"
        "|--------|-------------|\n"
        f"{rows}\n"
    )
    p = tmp_path / "README.md"
    p.write_text(text, encoding="utf-8")
    return p


FOLDER_A = "01 \U0001f6a8 Alerts"
FOLDER_B = "02 \U0001f4e9 Curated"


def test_matching_readme_and_opml_pass(tmp_path: Path) -> None:
    opml = _write_opml(tmp_path, {FOLDER_A: 3, FOLDER_B: 2})
    readme = _write_readme(tmp_path, 5, 2, [FOLDER_A, FOLDER_B])
    assert check_readme(readme, opml) == []


def test_feed_count_mismatch_is_reported(tmp_path: Path) -> None:
    opml = _write_opml(tmp_path, {FOLDER_A: 3, FOLDER_B: 2})
    readme = _write_readme(tmp_path, 99, 2, [FOLDER_A, FOLDER_B])
    errs = check_readme(readme, opml)
    assert any(e.rule == "readme-feed-count-mismatch" for e in errs)


def test_folder_count_mismatch_is_reported(tmp_path: Path) -> None:
    opml = _write_opml(tmp_path, {FOLDER_A: 1, FOLDER_B: 1})
    readme = _write_readme(tmp_path, 2, 7, [FOLDER_A, FOLDER_B])
    errs = check_readme(readme, opml)
    assert any(e.rule == "readme-folder-count-mismatch" for e in errs)


def test_folder_in_opml_missing_from_readme(tmp_path: Path) -> None:
    opml = _write_opml(tmp_path, {FOLDER_A: 1, FOLDER_B: 1})
    readme = _write_readme(tmp_path, 2, 2, [FOLDER_A])
    errs = check_readme(readme, opml)
    assert any(
        e.rule == "readme-folder-missing" and FOLDER_B in e.message for e in errs
    )


def test_folder_in_readme_missing_from_opml(tmp_path: Path) -> None:
    opml = _write_opml(tmp_path, {FOLDER_A: 1})
    readme = _write_readme(tmp_path, 1, 1, [FOLDER_A, FOLDER_B])
    errs = check_readme(readme, opml)
    assert any(
        e.rule == "readme-folder-extra" and FOLDER_B in e.message for e in errs
    )


def test_real_readme_parses_real_feeds_xml() -> None:
    """Smoke: the real pair must parse without raising.

    The folder-name table in README is advisory in CI and may drift between
    syncs, so this test does not assert an empty error list.
    """
    check_readme(Path("README.md"), Path("feeds.xml"))
