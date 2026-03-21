# Information and Cyber Security RSS/Atom Feeds

A curated collection of ~440 information security and cybersecurity RSS/Atom feeds organized in a single OPML file. Designed for import into any RSS reader (tested with [Inoreader](https://www.inoreader.com)).

Maintained by [Federico Maggi](https://github.com/phretor) (@phretor).

## Quick Start

Import `feeds.xml` into your RSS reader. That's it.

## Folders

Feeds are organized into flat (non-nested) folders with emoji prefixes for visual categorization. Flat structure is intentional — some readers (e.g., Inoreader) don't support nested folders.

| Folder | Description |
|--------|-------------|
| 📩 Infosec \| Newsletter | Curated security newsletters and digests |
| 🔐 Infosec \| Top | Essential reads — Krebs, Schneier, BleepingComputer, Dark Reading, etc. |
| 🧩 Malware \| Capabilities | Malware analysis tooling (capa, MBC) |
| 🐦 Infosec \| Reddits | Security-related subreddits |
| 🔏 Infosec \| Curated | Hand-picked curated sources |
| 💰 Infosec \| Breaches | Breach notifications and tracking |
| 💎 Infosec \| Boutiques | Security boutique firms and research labs |
| 🔬 Infosec \| Research & Tech Blogs | Vendor and independent security research |
| 🚀 Infosec \| Startups & Small Vendors | Emerging security companies |
| 🔊 Infosec \| Conferences | Security conference news |
| 🤦‍♂️ Infosec \| People 2 | Individual security researchers and bloggers |
| 📄 Infosec \| Papers | Academic journals and preprints (IEEE, ACM, arXiv) |
| 🌐 Infosec \| Blogs | Broad collection of security blogs |
| 🗞 Infosec \| Generic News | General security news outlets |
| 👩‍💻 Tech \| Curated 2 | Curated tech aggregators (Techmeme, HN) |
| ℹ ISACs | Information Sharing and Analysis Centers |
| 💻 Coding 2 | Developer-focused feeds (GitHub) |
| 🎯 Infosec \| Communities | Security community sites and mailing lists |
| ⚔️ Infosec \| Orgs & No-profits | EFF, OWASP, ISRG, Let's Encrypt |
| 🚔 Infosec \| LEA, GOV, CERT | Government CERTs, law enforcement, NIST |
| 👾 Infosec \| Hardware | Firmware and hardware security |
| ◀️ Infosec \| Reversing | Reverse engineering blogs and tools |
| 🏦 Trend Micro Blogs | Trend Micro research |
| 🏢 Infosec \| Enterprises | Large security vendor blogs |
| 🆘 Infosec \| Alerts and Advisories | CISA, NVD, vendor advisories |
| 🔒 Infosec \| Privacy | Privacy-focused tools and news |
| 🏛 Tech \| Top Companies | Major tech company blogs |
| 🔎 Investigative Journals | Investigative journalism (ProPublica, ICIJ, The Intercept) |
| 📟 Hardware & IoT | IoT, embedded systems, SDR |
| Infosec \| Feeds | Exploit databases and vulnerability feeds |
| Tech \| News | General technology news |
| Software \| Operating Systems | OS releases and updates |
| Science | Science news |

## Maintenance

This repo includes Python scripts (managed with [uv](https://docs.astral.sh/uv/)) for feed maintenance:

```bash
# Show feed statistics
uv run python -m scripts.stats

# Check all feeds for broken URLs
uv run python -m scripts.check_feeds

# Add a single feed
uv run python -m scripts.add_feeds \
  --name "Example Blog" \
  --xml-url "https://example.com/feed" \
  --html-url "https://example.com" \
  --folder "🌐 Infosec | Blogs"

# Bulk import from another OPML file
uv run python -m scripts.add_feeds --from-opml other.opml --target-folder "🌐 Infosec | Blogs"

# List available folders
uv run python -m scripts.add_feeds --list-folders
```

## Contributing

Contributions are welcomed — fork and send pull requests. New feeds should be placed in the appropriate existing category folder.

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
