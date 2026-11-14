# Information and Cyber Security RSS/Atom Feeds

A curated collection of 786 information security, cybersecurity, technology, and research RSS/Atom
feeds organized in a single OPML file. The taxonomy is ordered by reading action and urgency and is
designed for import into any RSS reader (tested with
[Inoreader](https://www.inoreader.com)).

Maintained by [Federico Maggi](https://github.com/phretor) (@phretor).

## Quick Start

Import `feeds.xml` into your RSS reader. That's it.

## Folders

Feeds are organized into 24 permanent, flat folders. Numeric prefixes make readers that sort folders
alphabetically preserve the intended workflow. The flat structure is intentional because some readers
do not support nested folders.

| Folder | Description |
|--------|-------------|
| 01 🚨 Alerts & Advisories | Time-sensitive vulnerability, incident, breach, and vendor advisories |
| 02 📩 Curated Editions & Podcasts | Bounded newsletters, editorial digests, and security podcasts |
| 03 🔐 Platform, Firmware & RoT | UEFI, secure boot, firmware, silicon, platform trust, and roots of trust |
| 04 🏭 OT & ICS Security | Operational technology, industrial control systems, and cyber-physical security |
| 05 ⚔️ Vulnerability & Exploit Research | Vulnerability discovery, exploitation, offensive research, and red teaming |
| 06 🔗 Software Supply Chain & AppSec | Application, cloud, dependency, and software supply-chain security |
| 07 🕵️ Threat Intel, Malware & Detection | Threat intelligence, malware analysis, detection, and incident research |
| 08 ◀️ Reverse Engineering & DFIR | Binary analysis, reverse engineering, digital forensics, and incident response |
| 09 🧠 AI & Agent Security | Security testing and abuse analysis of AI and agent systems |
| 10 🛡️ Standards & Governance | Standards, policy, compliance, coordination, and ecosystem governance |
| 11 🔏 Privacy, Crypto & Digital Rights | Privacy, cryptography, digital rights, and secure communications |
| 12 📄 Security Papers & Preprints | Academic journals, proceedings, papers, and preprints |
| 13 🔊 Conferences, CFPs & Talks | Conference announcements, calls for papers, programs, and talks |
| 14 🗞️ Security News & Reporting | Security reporting, analysis, and commentary |
| 15 ✍️ Independent Blogs & Commentary | Independent researcher and practitioner blogs |
| 16 🧪 Vendor, Labs & Advisory Feeds | Vendor labs, research teams, and advisory feeds |
| 17 💼 Business & Markets | Technology business, funding, infrastructure markets, and executive coverage |
| 18 📡 Security Linkstream | High-volume security aggregation and discovery streams |
| 19 🔩 Hardware, Maker & IoT | General hardware, embedded systems, maker projects, SDR, and IoT |
| 20 ☁️ Hyperscalers | Product news and engineering updates from major public-cloud platforms |
| 21 🌩️ Neo-clouds | AI-native and GPU-focused cloud infrastructure providers |
| 22 💻 Tech, AI & Science | General technology, engineering, AI, and science coverage |
| 23 📌 Personal & Misc | Personal and cross-domain writing without a stable operational mode |
| 24 🌴 Local News | Local and regional news coverage |

The live Miniflux instance retains an empty `00 🧪 Review Queue` for future triage. Miniflux omits
empty categories from OPML exports, so the folder is not present in `feeds.xml` while it is empty.

## Automated Miniflux sync

`feeds.xml` is kept in sync with the live Miniflux taxonomy by a weekly GitHub Actions workflow
(`.github/workflows/miniflux-sync.yml`, also runnable via `workflow_dispatch`). The workflow fetches
Miniflux's OPML export, normalizes it, and — on a real diff — opens or updates a single long-lived
PR on `bot/miniflux-sync` with the patched `feeds.xml`, README counts, and a mechanical CHANGELOG
entry. A separate downstream job runs `scripts.check_feeds` after sync has opened its
PR; the health job is report-only and cannot change sync's result or block that PR.
PR health is also report-only. GitHub runners have different IPs from readers and
publishers may block them, so runner HTTP results are **client-specific supplementary
evidence**, never a CI verdict—even a runner 404/410 is surfaced for human review,
not a red check. Both health jobs have a 25-minute timeout.

The runner probe fetches every feed with a feed-aware User-Agent and Accept header,
follows redirects, supports Brotli/gzip, caps decoded bodies at 16 MiB, and retries
transport/429/5xx failures twice with 0.3/0.6s backoff (24 workers, 4s connect/6s
read timeouts). HTTP 2xx is healthy only with complete parseable RSS/Atom XML;
404/410 is gone **from that client**, 403 or a CAPTCHA/JS challenge is blocked-to-
this-client, and network failures/429/5xx/oversized bodies are unreachable now.
Malformed XML or HTML is reported separately with response headers, a short
decoded-byte sample and XML parser error; it is not proof of a dead feed.

With credentials, the job reads Miniflux subscriptions, synchronously refreshes
feeds with errors or flagged by the runner (`PUT /v1/feeds/{id}/refresh`, up to six
concurrent requests with 45s timeouts), waits briefly, and re-reads `/v1/feeds`.
Only successfully refreshed feeds whose updated state is observable yield an
**in-cluster authoritative** health result; stale counters, unavailable refresh,
and feeds not refreshed yield no in-cluster verdict. Refresh failure never blocks
the report. Fork PRs lack Miniflux secrets and show runner evidence only, explicitly
without an authoritative verdict. `--base-opml` annotates new PR feeds;
`--min-error-count` filters historical Miniflux annotations. The optional
`--fail-on-dead` remains for **manual local use only**; CI never supplies it.

`normalize_opml` writes a canonical order, not Miniflux's response order: folders sort by their
`text` (the numeric prefixes encode the taxonomy order), and feeds inside each folder sort
case-insensitively by `text` (falling back to `title`), with `xmlUrl` as the tiebreaker. Normalization
is idempotent, and the sync compares the normalized form of both sides, so a response that differs
only in ordering produces no diff and no PR.

The same workflow also runs when a merge to `main` changes `feeds.xml`. It first subscribes
Miniflux to the feeds that merge added (`scripts.miniflux_push`: additive only — it never removes,
moves, renames, or edits existing feeds, never creates categories, skips feeds Miniflux already
has, and ignores merges of the sync PR itself), then runs the sync above so the sync PR reflects
the result.

For a one-time repair of the verified 2026-11-01 feed failures, dispatch
`.github/workflows/miniflux-maintenance.yml`. It defaults to a read-only dry run and
prints every proposed URL repoint/deletion; apply requires both `dry_run=false` and
`confirm=apply`. Review the dry-run log and obtain approval before applying: the
script changes Miniflux directly (eight URL repoints and thirteen deletions,
including both Project Zero blogger aliases; the canonical Project Zero feed
is already subscribed and stays untouched); it does not edit `feeds.xml`. Missing URLs or
replacement collisions stop mutation rather than selecting a different feed.
Feeds that Miniflux cannot fetch due to bot protection remain subscribed; each health
check reports the runner's live result as `blocked-to-this-client` if it encounters a
403 or challenge, without a hard-coded URL exemption.

## Structural lint

`uv run python -m scripts.lint_opml` checks `feeds.xml` beyond well-formed XML. Errors fail the
command and the PR structural-lint check. Warnings are printed and do not change the exit code.

Duplicate `xmlUrl` values are an error when they match after normalization: `http` and `https`
are the same, host case is ignored, one leading `www.` host label is ignored, and a trailing
slash is ignored. The query string is kept and the fragment is dropped. That key matches
`scripts.miniflux_push.url_key`, plus the `www.` stripping; the push script itself is unchanged.
Two www-only aliases already subscribed in Miniflux (Claroty Team82 and MalwareTech) are
warnings while that exact URL set is unchanged, because a pull request cannot delete them and
the next sync would restore a deletion. Any other normalized `xmlUrl` collision is an error.
A repeated `htmlUrl` under the same normalization is a warning, because one site can publish
more than one feed. An `xmlUrl` that uses cleartext `http://` is a warning.

## Suggesting feeds

Pull requests that add feeds to existing folders are welcome: a merged addition is pushed into
Miniflux, so the next sync keeps it. Removals, moves, and metadata fixes go through an issue, since
Miniflux is the source of truth and the next sync would revert them:

- **Suggest a feed** — open a PR, or propose a new feed with its URL and category in an issue
- **Report a problem** — a feed is dead, misplaced, duplicated, or has wrong metadata

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full policy and [SECURITY.md](SECURITY.md) for
reporting security concerns.

## Credits

<table>
  <tbody>
    <tr>
      <td align="center"><a href="https://github.com/glaucusec"><img src="https://avatars.githubusercontent.com/u/67792905?v=4" width="100px;" alt=""/><br /><sub><b>Abhishek</b></sub></a><br /></td>
      <td align="center"><a href="https://diablohorn.com">DiabloHorn</a></td>
    </tr>
  </tbody>
</table>

## License

MIT License
