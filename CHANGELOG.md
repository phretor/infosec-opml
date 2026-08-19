# Changelog

## 2026-08-18

### Changed
- Exported the reconciled live Miniflux inventory into `feeds.xml`
- Replaced the 26-folder source-type layout with 17 action-oriented folders plus a temporary Review Queue
- Added numeric folder prefixes so alphabetical readers preserve the intended triage-to-context workflow
- Classified every existing subscription into exactly one destination; retained five repair/review candidates in `00 🧪 Review Queue`
- Removed four repository-only subscriptions while reconciling to the 358-feed Miniflux inventory

### Net result
- 358 feeds across 18 flat folders

## 2026-07-11

### Removed
- 9 dead vulnerability/advisory feeds (404/DNS failures)
- 12 more dead feeds across all folders; updated Sophos feed URL

### Added
- 45 new feeds sourced from personal Obsidian vault bookmarks

### Net result
- 461 feeds across 14 folders (was 438)

## 2026-04-24

### Changed
- Restructured folder taxonomy from 33 source-type folders to 14 topic-oriented folders
- Folder assignment now driven by content topic, not org type
- High-frequency sources quarantined into `Alerts & Advisories` and `News & Media`

### Added
- `scripts/classify_feeds.py`, improved `check_feeds.py`
- New feeds: Calif, Joe T. Sylve Ph.D., devansh

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
