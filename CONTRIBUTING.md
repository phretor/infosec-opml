# Contributing

Thanks for your interest. This repository is a published export of a curated feed list, so the
contribution model is different from most code projects.

## The source of truth is Miniflux, not `feeds.xml`

The feed list is maintained inside a private [Miniflux](https://miniflux.app) instance. A scheduled
GitHub Actions workflow regenerates `feeds.xml`, `README.md`, and `CHANGELOG.md` from the Miniflux
taxonomy and opens a sync PR. Any hand-edit to `feeds.xml` would be overwritten by the next sync.

**This repository does not accept pull requests.** They will be closed without merging.

## What you can do

Open a GitHub issue:

- **[Suggest a feed](../../issues/new?template=feed_suggestion.yml)** — a feed you think belongs
  here, with its URL and a note on which category fits
- **[Report a problem](../../issues/new?template=bug_report.yml)** — a feed is dead, misplaced in
  the wrong category, duplicated, or has wrong metadata

Both templates are structured forms so triage stays fast.

## For strangers who want to fork

The repo is MIT-licensed. Fork freely and run your own curated list; the sync workflow is designed
to be reusable with your own Miniflux instance (set `MINIFLUX_URL` and `MINIFLUX_TOKEN` in your
fork's secrets).

## Security concerns

Please follow [SECURITY.md](SECURITY.md), not this file, for anything security-related — including
a feed in this list that starts distributing malware or C2 content.
