# Changelog

## 2026-08-18

### Changed
- Reverted 14-topic taxonomy back to source-type folders (26 folders with emoji prefixes)
- Synced feeds.xml from Papr database (362 feeds)
- Renamed `Infosec` folders to `Security`, merged Trend Micro Blogs into Enterprises
- Added folders: AI, Distro, GitHub, Science
- Restored pretty-printed XML with `title` and `htmlUrl` attributes on all feeds

### Net result
- 362 feeds across 26 folders

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
