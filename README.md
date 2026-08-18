# Information and Cyber Security RSS/Atom Feeds

A curated collection of ~360 information security and cybersecurity RSS/Atom feeds organized in a
single OPML file. Designed for import into any RSS reader (tested with
[Inoreader](https://www.inoreader.com)).

Maintained by [Federico Maggi](https://github.com/phretor) (@phretor).

## Quick Start

Import `feeds.xml` into your RSS reader. That's it.

## Folders

Feeds are organized into flat (non-nested) folders with emoji prefixes for visual categorization. Flat structure is intentional — some readers (e.g., Inoreader) don't support nested folders.

| Folder | Description |
|--------|-------------|
| 📩 Security \| Newsletter | Curated security newsletters and digests |
| 🔐 Security \| Top | Essential reads -- Krebs, Schneier, BleepingComputer, Dark Reading, etc. |
| 💰 Security \| Breaches | Breach notifications and tracking |
| 🚀 Security \| Companies | Security company blogs |
| 🔊 Security \| Conferences | Security conference news |
| 🤦‍♂️ Security \| People | Individual security researchers and bloggers |
| 📄 Security \| Papers | Academic journals and preprints (IEEE, ACM, arXiv) |
| 🌐 Security \| Blogs | Broad collection of security blogs |
| 🗞 Security \| Generic News | General security news outlets |
| 🎯 Security \| Communities | Security community sites and mailing lists |
| ⚔️ Security \| Orgs & No-profits | EFF, OWASP, ISRG, Let's Encrypt |
| 🚔 Security \| LEA, GOV, CERT | Government CERTs, law enforcement |
| 👾 Security \| Hardware | Firmware and hardware security |
| ◀️ Security \| Reversing | Reverse engineering blogs and tools |
| 🏢 Security \| Enterprises | Large security vendor blogs |
| 🆘 Security \| Alerts and Advisories | CISA, vendor advisories, CVE feeds |
| 🔒 Security \| Privacy | Privacy-focused tools and news |
| 🏛 Tech \| Top Companies | Major tech company blogs |
| 👩‍💻 Tech \| Curated 2 | Curated tech aggregators (Techmeme, HN) |
| 💻 Coding 2 | Developer-focused feeds (GitHub) |
| 📟 Hardware & IoT | IoT, embedded systems, SDR |
| Tech \| News | General technology news |
| AI | AI labs and research (OpenAI, Anthropic, Hugging Face) |
| Distro | Linux distribution news (Debian, Ubuntu) |
| GitHub | GitHub trending repositories |
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
  --folder "🌐 Security | Blogs"

# Bulk import from another OPML file
uv run python -m scripts.add_feeds --from-opml other.opml --target-folder "🌐 Security | Blogs"

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
