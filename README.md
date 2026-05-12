# Information and Cyber Security RSS/Atom Feeds

A curated collection of ~438 information security and cybersecurity RSS/Atom feeds organized in a single OPML file. Designed for import into any RSS reader (tested with [Inoreader](https://www.inoreader.com)).

Maintained by [Federico Maggi](https://github.com/phretor) (@phretor).

## Quick Start

Import `feeds.xml` into your RSS reader. That's it.

## Folders

Feeds are organized into 14 flat topic-oriented folders. Flat structure is intentional — some readers (e.g., Inoreader) don't support nested folders.

Folders are ordered: fast-skim tier first, then topic tier, then slow-read tier.

| Folder | What's in it |
|--------|-------------|
| Alerts & Advisories | CERTs, CISA, patch advisories, CVE feeds |
| News & Media | Journalism, news aggregators, general tech media |
| Exploitation & Vuln Research | CVE analysis, PoC, pre-auth RCEs, exploit chain research |
| Malware & Threat Intel | Malware analysis, CTI, threat actors, ransomware, dark web |
| Reverse Engineering | Binary analysis, disassembly, deobfuscation, RE tooling |
| Offensive Security | Red team, C2, pentesting TTPs, adversary simulation |
| Cloud & Supply Chain | Cloud infra security, containers, k8s, CI/CD, dependency attacks |
| Hardware, Embedded & ICS | Firmware, IoT, OT/SCADA, RF, hardware hacking |
| Cryptography & Privacy | TLS, PKI, PQC, digital rights, identity, data protection |
| Forensics & Incident Response | DFIR, memory forensics, threat hunting, IR tooling |
| Application Security | Web vulns, SAST, API security, secure dev, LLM security |
| Research & Papers | arXiv cs.CR, IEEE, ACM, academic journals |
| Newsletters & Digests | Curated weekly/periodic digests and newsletters |
| General & Mixed | Personal blogs spanning multiple topics |

**Assignment rule:** folder is determined by topic, not source type. A vendor blog and a solo researcher publishing malware analysis both belong in Malware & Threat Intel.

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

Contributions are welcomed — fork and send pull requests. New feeds should be placed in the appropriate topic folder. If unsure, run `/classify-feeds <url>` in Claude Code to get a placement suggestion.

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
