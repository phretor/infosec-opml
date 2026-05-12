---
model: claude-haiku-4-5-20251001
description: Add a new infosec source — discovers feed URL, quality-gates it, classifies it, and inserts it into feeds.xml
---

Add a new RSS/Atom source to feeds.xml. `$ARGUMENTS` is a website URL or direct feed URL.

## Step 1 — Discover feed URL

```bash
python3 - << 'EOF'
import urllib.request, re, sys
from urllib.parse import urljoin
url = sys.argv[1] if len(sys.argv) > 1 else ""
headers = {"User-Agent": "Mozilla/5.0"}
feed_re = re.compile(r'<link[^>]+type="application/(rss|atom)\+xml"[^>]+href="([^"]+)"', re.I)
try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read(8192).decode("utf-8", errors="ignore")
    m = feed_re.search(body)
    if m:
        fu = m.group(2)
        print("FEED:", fu if fu.startswith("http") else urljoin(url, fu))
    else:
        print("NOT_FOUND")
except Exception as e:
    print("ERROR:", e)
EOF
```

Replace `sys.argv[1]` with the actual URL from `$ARGUMENTS`. If `NOT_FOUND`, try appending `/feed`, `/rss.xml`, `/atom.xml`, `/feed.xml` to the base domain one at a time until one returns valid XML.

## Step 2 — Fetch 3 recent articles

```bash
curl -sL --max-time 12 "FEED_URL" | python3 /tmp/parse_feed.py
```

If `/tmp/parse_feed.py` is missing, create it:

```bash
cat > /tmp/parse_feed.py << 'EOF'
import sys, xml.etree.ElementTree as ET, re
strip = lambda s: re.sub(r"<[^>]+>", " ", s or "").strip()[:250]
try:
    root = ET.fromstring(sys.stdin.read())
    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for it in items[:3]:
        t = (it.findtext("title") or it.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        d = strip(it.findtext("description") or it.findtext("{http://www.w3.org/2005/Atom}summary") or "")
        print(f"- {t}")
        if d: print(f"  {d}")
except Exception as e:
    print(f"ERROR: {e}")
EOF
```

## Step 3 — Quality gate

Evaluate all four. **Reject** if two or more fail.

1. **Original** — publishes original research, reporting, or analysis (not pure reposts/aggregation)
2. **Technical depth** — goes beyond headlines at least occasionally: PoC, code, methodology, or detailed analysis
3. **Relevant** — primary topic is information security, cryptography, or adjacent offensive/defensive infra
4. **Active** — at least one article in the last 90 days

Print `PASS` or `REJECT: <reason>`. If REJECT, stop here.

## Step 4 — Classify

Assign:
- **Tags** (1–3): `app` `exp` `mal` `net` `cloud` `sys` `rev` `social` `for` `ics` `crypto`
- **Folder** — exact name, pick one:
  `Alerts & Advisories` · `News & Media` · `Exploitation & Vuln Research` · `Malware & Threat Intel` ·
  `Reverse Engineering` · `Offensive Security` · `Cloud & Supply Chain` · `Hardware, Embedded & ICS` ·
  `Cryptography & Privacy` · `Forensics & Incident Response` · `Application Security` ·
  `Research & Papers` · `Newsletters & Digests` · `General & Mixed`
- **Confidence**: high | medium | low
- One-sentence rationale

## Step 5 — Check for existing entry

```bash
python3 -c "
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
tree = ET.parse('feeds.xml')
domain = urlparse('FEED_URL').netloc.removeprefix('www.')
for folder in tree.getroot().find('body'):
    for f in folder:
        if domain in f.get('xmlUrl',''):
            print('DUPLICATE:', f.get('text'), '->', folder.get('text'), '->', f.get('xmlUrl'))
"
```

If a duplicate is found, report it and stop.

## Step 6 — Add to feeds.xml

```bash
uv run python -m scripts.add_feeds \
  --name "FEED_NAME" \
  --xml-url "FEED_URL" \
  --html-url "SITE_URL" \
  --folder "FOLDER_NAME"
```

Confirm with: added feed name, folder, tags, rationale.
