# Information and Cyber Security RSS/Atom Feeds

A curated collection of 366 information security, cybersecurity, technology, and research RSS/Atom
feeds organized in a single OPML file. The taxonomy is ordered by reading action and urgency and is
designed for import into any RSS reader (tested with
[Inoreader](https://www.inoreader.com)).

Maintained by [Federico Maggi](https://github.com/phretor) (@phretor).

## Quick Start

Import `feeds.xml` into your RSS reader. That's it.

## Folders

Feeds are organized into 21 permanent, flat folders. Numeric prefixes make readers that sort folders
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

## Maintenance

This repo includes Python scripts managed with [uv](https://docs.astral.sh/uv/):

```bash
# Show feed statistics
uv run python -m scripts.stats

# Check all feeds for broken URLs
uv run python -m scripts.check_feeds

# Add a single feed
uv run python -m scripts.add_feeds \
  --name "Example Research Blog" \
  --xml-url "https://example.com/feed" \
  --html-url "https://example.com" \
  --folder "04 ⚔️ Vulnerability & Exploit Research"

# Bulk import from another OPML file
uv run python -m scripts.add_feeds \
  --from-opml other.opml \
  --target-folder "03 🔐 Platform, Firmware & RoT"

# List available folders
uv run python -m scripts.add_feeds --list-folders
```

Validate structural changes before committing:

```bash
xmllint --noout feeds.xml
uv run python -m scripts.stats
```

## Contributing

Contributions are welcome—fork the repository and send a pull request. Place new feeds according to
their dominant reading action and content. Preserve the numeric prefix, emoji, and flat folder
structure.

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
