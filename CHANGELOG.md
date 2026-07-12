# Changelog

## 2026-07-11

### Removed
- 9 dead vulnerability/advisory feeds (404/DNS failures)
- 12 more dead feeds across all folders; updated Sophos feed URL

### Added
- 45 new feeds sourced from personal Obsidian vault bookmarks
- Infosec: abuse.ch, Gemini Advisory, Intezer, Curated Intelligence, Intel 471, Nextron Systems, Ulf Frisk, Grapl Security, Security Breached, RedHunt Labs, VoidSec, polarply, Shielder, Tamir Zahavi-Brunner, LeakIX, Malcat, Ken Shirriff's Blog, Comsecuris, bunnie's blog, Purism, CyberArk, SonarSource Blog, Parsiya.net, The Hacker News, DoublePulsar
- General/non-infosec: Oxide Computer, Raspberry Pi, Julia Evans, Drew DeVault, BBC Technology, Phys.org, and others

### Net result
- 461 feeds across 14 folders (was 438)

## 2026-04-24

### Changed
- Restructured folder taxonomy from 33 source-type folders to 14 topic-oriented folders
- Folder assignment now driven by content topic, not org type (vendor/enterprise/startup distinctions removed)
- High-frequency sources quarantined into `Alerts & Advisories` and `News & Media` to avoid drowning topic folders
- Old catch-all `🌐 Infosec | Blogs` (119 entries) dissolved; feeds redistributed by topic; `General & Mixed` replaces it with 24 entries

### Added
- `AGENTS.md` pointing to `CLAUDE.md` for agent compatibility
- `.claude/commands/classify-feeds.md` — Claude Code skill that fetches 3 articles per feed and proposes folder classification using Haiku
- `scripts/classify_feeds.py` — feed classification script (used by the skill)
- `scripts/check_feeds.py` — improved with `--remove` / `--remove-all` flags and dead-vs-transient error classification
- New feeds: Calif (`blog.calif.io`), Joe T. Sylve Ph.D. (`jtsylve.blog`), devansh (`devansh.bearblog.dev`)

### Net result
- 438 feeds across 14 folders (was 435 across 33)

## 2026-03-21

Major cleanup and expansion of the feed collection.

### Removed
- Entire "All Infosec | Relevant" folder (140 duplicate entries mirroring other folders)
- 83 dead feeds returning 4xx/5xx/DNS failures (FireEye, Vice, Motherboard, Threatpost, ToolsWatch, etc.)
- All Twitter and Telegram feeds (platforms killed RSS support)
- All kill-the-newsletter.com feeds (ephemeral bridges, expired)
- 5 empty folders: Reporters, Malware, Telegram, Tools, All Infosec | Relevant
- ~19 cross-folder duplicates (kept each feed in its most specific folder)

### Added
- 196 new feeds from [talkback.sh](https://talkback.sh) and [allinfosecnews](https://github.com/foorilla/allinfosecnews_sources), all verified reachable
- Notable additions: The Hacker News, SecurityWeek, Dark Reading, 404 Media, Unit 42, Rapid7, NIST, FortiGuard, Help Net Security, DFIR Report, GreyNoise, Red Canary, Datadog Security Labs, watchTowr Labs, and many more
- Python maintenance scripts (`scripts/`): `check_feeds.py`, `add_feeds.py`, `stats.py`
- uv project setup (`pyproject.toml`) for dependency and script management

### Fixed
- Security Affairs URL updated from `securityaffairs.co/wordpress/feed` to `securityaffairs.com/feed`
- `r/zeroday` htmlUrl corrected (was pointing to RSS URL instead of subreddit page)

### Net result
- 492 -> 443 feeds across 33 folders, all verified reachable
