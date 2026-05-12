# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A curated collection of ~440 information security and cybersecurity RSS/Atom feeds organized in a single OPML 1.0 file (`feeds.xml`). Designed for import into RSS readers like Inoreader. Maintained by Federico Maggi (@phretor).

## Repository Structure

- `feeds.xml` — The data file. An OPML 1.0 XML document containing all feed subscriptions organized into 14 flat topic-oriented folders (see Folder Taxonomy below).
- `README.md` — Project documentation, folder descriptions, maintenance instructions, credits.
- `CHANGELOG.md` — Log of notable changes to the feed collection.
- `scripts/` — Python maintenance scripts (managed with uv): `check_feeds.py`, `add_feeds.py`, `stats.py`, `fetch_cache.py`, `restructure_folders.py`.
- `.claude/commands/` — Claude Code slash commands: `classify-feeds.md` (classify feeds against taxonomy) and `secnews/` (new-source, lint, expand, hot, query).
- `LICENSE` — MIT License.

## Folder Taxonomy

14 flat folders, topic-first. Folders are ordered: fast-skim tier first, then topic tier, then slow-read tier.

| Folder | Purpose |
|---|---|
| `Alerts & Advisories` | CERTs, CISAs, patch advisories, CVE feeds — time-sensitive, low depth |
| `News & Media` | Journalism, news aggregators, general tech media |
| `Exploitation & Vuln Research` | CVE analysis, PoC, pre-auth RCEs, exploit chain research |
| `Malware & Threat Intel` | Malware analysis, CTI, threat actors, ransomware, dark web |
| `Reverse Engineering` | Binary analysis, disassembly, deobfuscation, RE tooling |
| `Offensive Security` | Red team, C2, pentesting TTPs, adversary simulation |
| `Cloud & Supply Chain` | Cloud infra security, containers, k8s, CI/CD, dependency attacks |
| `Hardware, Embedded & ICS` | Firmware, IoT, OT/SCADA, RF, hardware hacking |
| `Cryptography & Privacy` | TLS, PKI, PQC, digital rights, identity, data protection |
| `Forensics & Incident Response` | DFIR, memory forensics, threat hunting, IR tooling |
| `Application Security` | Web vulns, SAST, API security, secure dev, LLM security |
| `Research & Papers` | arXiv cs.CR, IEEE, ACM, academic journals |
| `Newsletters & Digests` | Curated weekly/periodic digests, newsletters |
| `General & Mixed` | Personal blogs covering multiple topics, practitioners |

## Folder assignment rules

1. **Topic determines folder, not source type.** A vendor blog, a research paper, and a newsletter about malware analysis all belong in `Malware & Threat Intel`. Never assign by org type (vendor/startup/enterprise/gov).
2. **High-frequency sources go in the skim tier.** News sites and advisory feeds that publish multiple items per day belong in `News & Media` or `Alerts & Advisories` regardless of content quality, so they don't bury lower-frequency deep research in topic folders.
3. **Each folder has a single browsing intent.** The question to ask: "If I open this folder, what am I in the mood to read?" The answer should be unambiguous.
4. **Mixed-topic sources go by primary beat.** A source covering everything is `News & Media`. A source that is 80% malware and 20% other is `Malware & Threat Intel`.
5. **`General & Mixed` is a last resort.** Use it only for personal blogs that genuinely span several topics with no dominant one. It should stay small.

## Working with feeds.xml

- The file is valid XML (OPML 1.0, UTF-8 encoded). Validate changes with `xmllint --noout feeds.xml` if available.
- Feeds are `<outline>` elements nested under folder `<outline>` elements within `<body>`.
- Each feed outline has attributes: `text`, `title`, `type="rss"`, `xmlUrl` (feed URL), and `htmlUrl` (site URL).
- Folders are flat (no nesting) for Inoreader compatibility. Do not introduce nested folder hierarchies.
- Folder names are plain text — no emoji prefixes.
- Use `uv run python -m scripts.stats` to check current feed counts and folder breakdown.
- Use `uv run python -m scripts.check_feeds` to verify feed health before committing.
- Use `/classify-feeds <url>` to classify a new source before adding it.

## Documentation

- When feeds are added or removed, update `README.md` to reflect the current feed count (~NNN) and folder list.
- When notable changes are made, add an entry to `CHANGELOG.md` with the date and a summary of what changed.

## Git Conventions

- Co-Authored-By lines must use `Claude <noreply@anthropic.com>` — do not include the model ID or version.

## Contributing

Fork and submit pull requests. New feeds should be placed in the appropriate topic folder per the taxonomy above. Use `/classify-feeds <url>` if unsure. Contributors are credited in README.md.
