<!--
Pull requests may only ADD feeds to existing folders in feeds.xml. A merged addition is
pushed into the maintainer's Miniflux instance, which is the source of truth for the list.

Removals, moves, metadata fixes, new folders, and code/workflow changes are not accepted as
PRs (the next Miniflux sync would revert them). Open an issue instead:
- Report a problem: https://github.com/phretor/infosec-opml/issues/new?template=bug_report.yml
- Suggest a feed:   https://github.com/phretor/infosec-opml/issues/new?template=feed_suggestion.yml

See CONTRIBUTING.md for the full policy.
-->

## Feeds added

<!-- One line per feed: name, feed URL, folder, and why it belongs. -->

-

## Checklist

- [ ] Only new `<outline>` entries in existing folders of `feeds.xml`; nothing removed, moved, or edited
- [ ] Each entry has `text`, `title`, `type="rss"`, `xmlUrl`, and `htmlUrl`
- [ ] `xmlUrl` is the final RSS/Atom URL (no redirect, not an HTML page) and is not already listed
- [ ] README feed count ("A curated collection of N …") bumped by the number of feeds added
- [ ] `CHANGELOG.md` untouched (it is generated)
