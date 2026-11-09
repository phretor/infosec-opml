# Information and Cyber Security RSS/Atom Feeds

A curated collection of 788 information security, cybersecurity, technology, and research RSS/Atom
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
entry. A separate downstream job runs `scripts.check_feeds --fail-on-dead` on the resulting
file; it cannot change the completed sync job or prevent its PR from opening. The check
directly fetches every feed from its runner with a feed-aware User-Agent and Accept header,
follows redirects, caps bodies at 8 MiB, and uses up to three attempts (0.3/0.6s backoff
for connection errors, timeouts, 429 and 5xx). It uses 24 workers, 4s connect/6s read
timeouts and a 25-minute job limit. A complete, parseable RSS/Atom response with HTTP 2xx
is healthy. Live 404/410 is gone and fails `--fail-on-dead`; 403 or a CAPTCHA/JS challenge
is blocked-to-this-client, not dead. Timeouts, network errors, 429, 5xx, bodies
exceeding the read cap, and other inconclusive statuses are unreachable now,
not dead. Invalid 2xx XML/HTML is reported separately, not treated as proof of
retirement. The report includes final redirect URL, HTTP status and retry count.
Miniflux error counters are optional historical
annotations, never verdicts; `--min-error-count` filters those annotations. `--base-opml`
marks PR additions without exempting them from live probing. Health checks run on fork PRs
without Miniflux credentials, as an independent advisory job.

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
