---
model: claude-haiku-4-5-20251001
description: Classify infosec RSS feed sources by fetching and analyzing their 3 most recent articles
---

Classify one or more RSS/Atom feeds against the feeds.xml taxonomy.

`$ARGUMENTS` may be one or more `xmlUrl` values. If empty, classify every feed currently in `feeds.xml`.

## Step 1 — resolve feed list

If no URLs were given, read feeds.xml:

```bash
python3 -c "
import xml.etree.ElementTree as ET
for folder in ET.parse('feeds.xml').getroot().find('body'):
    for feed in folder:
        url = feed.get('xmlUrl', '')
        if url:
            print(folder.get('text',''), '|', feed.get('text',''), '|', url)
"
```

## Step 2 — fetch 3 recent articles per feed

Reuse the shared parser from `secnews:new-source` (create `/tmp/parse_feed.py` if missing — see that skill for the body). Then for each feed:

```bash
curl -sL --max-time 10 "FEED_URL" | python3 /tmp/parse_feed.py
```

If a feed errors or returns no items, mark it `[FETCH ERROR]` and continue.

## Step 3 — classify each source

Using the feed name, current folder, and 3 article titles/snippets, assign:

**Tags** (1–3 from this list):

| tag     | scope |
|---------|-------|
| `app`   | application/web security, SAST, API security, LLM security |
| `exp`   | exploit development, CVE analysis, PoC, pre-auth RCEs |
| `mal`   | malware, ransomware, CTI, threat actors, dark web |
| `net`   | network security, traffic analysis, protocols |
| `cloud` | cloud infra, AWS/GCP/Azure, containers, k8s, CI/CD, supply chain |
| `sys`   | OS/kernel, Windows/Linux/macOS internals, privesc |
| `rev`   | reverse engineering, binary analysis, disassembly, RE tooling |
| `social`| phishing, social engineering, OSINT |
| `for`   | forensics, DFIR, memory analysis, threat hunting |
| `ics`   | OT/ICS/SCADA, firmware, IoT, RF, hardware |
| `crypto`| cryptography, PKI, TLS, post-quantum, privacy |

**Folder** — exact name from the 14-folder taxonomy (see `CLAUDE.md`):

`Alerts & Advisories` · `News & Media` · `Exploitation & Vuln Research` · `Malware & Threat Intel` · `Reverse Engineering` · `Offensive Security` · `Cloud & Supply Chain` · `Hardware, Embedded & ICS` · `Cryptography & Privacy` · `Forensics & Incident Response` · `Application Security` · `Research & Papers` · `Newsletters & Digests` · `General & Mixed`

**Confidence:** `high` | `medium` | `low`

**Rationale:** one sentence.

Apply the folder assignment rules from `CLAUDE.md`: topic determines folder (not source type); high-frequency sources go to the skim tier; `General & Mixed` is a last resort.

## Step 4 — output

```
[→ MOVE] Feed Name
  tags: app, rev   confidence: high
  current:   General & Mixed
  suggested: Reverse Engineering
  Focused on macOS kernel research and binary analysis.

[  OK  ] Other Feed Name
  tags: mal, net   confidence: high
  current:   Malware & Threat Intel
  Publishes threat intel and malware campaign breakdowns.
```

End with a **MOVE SUMMARY** listing only feeds where `current ≠ suggested`, grouped by suggested folder.

**Do not modify feeds.xml until the user explicitly confirms.**
