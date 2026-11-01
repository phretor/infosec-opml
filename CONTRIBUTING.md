# Contributing

Thanks for your interest. This repository is a published export of a curated feed list, so the
contribution model is different from most code projects.

## The source of truth is Miniflux, not `feeds.xml`

The feed list is maintained inside a private [Miniflux](https://miniflux.app) instance. A GitHub
Actions workflow regenerates `feeds.xml`, `README.md` counts, and `CHANGELOG.md` from the Miniflux
taxonomy and opens a sync PR. The sync also runs the other way for one kind of change only: when a
pull request that **adds** feeds is merged, the workflow subscribes Miniflux to those feeds, so the
next sync keeps them. Nothing else flows from the repo into Miniflux.

## Suggest a feed with a pull request

A pull request may only add feeds. Edit `feeds.xml` and:

- Add one `<outline>` per feed inside the existing folder that fits best, with all five attributes:

  ```xml
  <outline text="Feed Name" title="Feed Name" type="rss" xmlUrl="https://example.com/feed.xml" htmlUrl="https://example.com/"></outline>
  ```

- Use the final RSS/Atom URL (not an HTML page, not a URL that redirects), served over http(s) from
  a public host name.
- Do not add a feed that is already listed, and do not create new folders.
- Bump the feed count in the README sentence "A curated collection of N information security…" by
  the number of feeds you add.
- Do not edit `CHANGELOG.md`; it is generated.
- Say in the PR description why each feed belongs (publication cadence, author, topic focus).

The PR checks reject anything else: removing, moving, renaming, or editing an existing feed, or
adding a feed to a folder that does not exist yet. After merge, Miniflux may normalize the feed's
title, site URL, and position within its folder; the next sync PR carries that back.

## Everything else goes through an issue

Removals, moves, and metadata fixes cannot be merged as PRs because Miniflux is the source of truth
and the next sync would revert them. Pull requests that change scripts, workflows, or docs are not
accepted either. Open an issue instead:

- **[Report a problem](../../issues/new?template=bug_report.yml)** — a feed is dead, misplaced in
  the wrong category, duplicated, or has wrong metadata
- **[Suggest a feed](../../issues/new?template=feed_suggestion.yml)** — if you prefer not to open a
  PR, the structured form works too
- A new folder — describe it in an issue; the maintainer creates folders in Miniflux

## For strangers who want to fork

The repo is MIT-licensed. Fork freely and run your own curated list; the sync workflow is designed
to be reusable with your own Miniflux instance (set `MINIFLUX_URL` and `MINIFLUX_TOKEN` in your
fork's secrets).

## Security concerns

Please follow [SECURITY.md](SECURITY.md), not this file, for anything security-related — including
a feed in this list that starts distributing malware or C2 content.
