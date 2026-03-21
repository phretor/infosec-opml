# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A curated collection of ~440 information security and cybersecurity RSS/Atom feeds organized in a single OPML 1.0 file (`feeds.xml`). Designed for import into RSS readers like Inoreader. Maintained by Federico Maggi (@phretor).

## Repository Structure

- `feeds.xml` — The data file. An OPML 1.0 XML document containing all feed subscriptions organized into ~33 flat (non-nested) folders identified by emoji prefixes (e.g., `🔐 Infosec | Top`, `🌐 Infosec | Blogs`).
- `README.md` — Project documentation, folder descriptions, maintenance instructions, credits.
- `CHANGELOG.md` — Log of notable changes to the feed collection.
- `scripts/` — Python maintenance scripts (managed with uv): `check_feeds.py`, `add_feeds.py`, `stats.py`.
- `LICENSE` — MIT License.

## Working with feeds.xml

- The file is valid XML (OPML 1.0, UTF-8 encoded). Validate changes with `xmllint --noout feeds.xml` if available.
- Feeds are `<outline>` elements nested under folder `<outline>` elements within `<body>`.
- Each feed outline has attributes: `text`, `title`, `type="rss"`, `xmlUrl` (feed URL), and `htmlUrl` (site URL).
- Folders are flat (no nesting) for Inoreader compatibility. Do not introduce nested folder hierarchies.
- Folder names use emoji prefixes for visual categorization — preserve this convention when adding folders.
- Use `uv run python -m scripts.stats` to check current feed counts and folder breakdown.
- Use `uv run python -m scripts.check_feeds` to verify feed health before committing.

## Documentation

- When feeds are added or removed, update `README.md` to reflect the current feed count (~NNN) and folder list.
- When notable changes are made, add an entry to `CHANGELOG.md` with the date and a summary of what changed.

## Git Conventions

- Co-Authored-By lines must use `Claude <noreply@anthropic.com>` — do not include the model ID or version.

## Contributing

Fork and submit pull requests. New feeds should be placed in the appropriate existing category folder. Contributors are credited in README.md.
