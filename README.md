# Information and Cyber Security RSS/Atom Feeds

A curated collection of 800 information security, cybersecurity, technology, and research RSS/Atom
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
| 14 🗞️ Security News & Commentary | Security reporting, analysis, and commentary |
| 15 💼 Business & Markets | Technology business, funding, infrastructure markets, and executive coverage |
| 16 📡 Security Linkstream | High-volume security aggregation and discovery streams |
| 17 🔩 Hardware, Maker & IoT | General hardware, embedded systems, maker projects, SDR, and IoT |
| 18 ☁️ Hyperscalers | Product news and engineering updates from major public-cloud platforms |
| 19 🌩️ Neo-clouds | AI-native and GPU-focused cloud infrastructure providers |
| 20 💻 Tech, AI & Science | General technology, engineering, AI, and science coverage |
| 21 📌 Personal & Misc | Personal and cross-domain writing without a stable operational mode |

The live Miniflux instance retains an empty `00 🧪 Review Queue` for future triage. Miniflux omits
empty categories from OPML exports, so the folder is not present in `feeds.xml` while it is empty.

## Automated Miniflux sync

`feeds.xml` is kept in sync with the live Miniflux taxonomy by a weekly GitHub Actions workflow
(`.github/workflows/miniflux-sync.yml`, also runnable via `workflow_dispatch`). The workflow fetches
Miniflux's OPML export, normalizes it, and — on a real diff — opens or updates a single long-lived
PR on `bot/miniflux-sync` with the patched `feeds.xml`, README counts, and a mechanical CHANGELOG
entry. A second job runs `scripts.check_feeds --fail-on-dead` against the resulting file. Health
status is read from Miniflux's own `/v1/feeds` API (not probed from the GitHub runner), so the gate
reflects whether Miniflux can actually fetch each feed. Dead feeds (disabled, over the parsing-error
threshold, or missing from Miniflux) block the PR as a red check. Transient errors, feeds over
the threshold whose last error is a temporary reachability failure (network/DNS error, timeout, HTTP
429 or 5xx), and, in PR checks, feeds added by the PR that Miniflux has not subscribed to yet are
reported but do not.

The same workflow also runs when a merge to `main` changes `feeds.xml`. It first subscribes
Miniflux to the feeds that merge added (`scripts.miniflux_push`: additive only — it never removes,
moves, renames, or edits existing feeds, never creates categories, skips feeds Miniflux already
has, and ignores merges of the sync PR itself), then runs the sync above so the sync PR reflects
the result.

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
