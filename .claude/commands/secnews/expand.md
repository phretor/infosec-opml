---
description: Expand a folder by finding new sources — searches the web and curated feeds, presents candidates, then calls new-source on selected ones
---

Expand a folder in feeds.xml with new quality sources.

`$ARGUMENTS` is the folder name to expand (e.g. `Reverse Engineering`). If empty, ask the user which folder to expand.

## Step 1 — Load current folder contents

```bash
python3 -c "
import xml.etree.ElementTree as ET
target = '$ARGUMENTS'
tree = ET.parse('feeds.xml')
for folder in tree.getroot().find('body'):
    if folder.get('text','').lower() == target.lower():
        for f in folder:
            print(f.get('xmlUrl',''), '|', f.get('text',''))
"
```

Extract: the domains already present (to avoid suggesting duplicates), and the rough content pattern of existing feeds.

## Step 2 — Search for candidates

Use WebSearch with 3–4 targeted queries. Vary the angles:
- Community-curated lists: `site:reddit.com/r/netsec "best blogs" TOPIC`
- OPML/RSS discovery: `"opml" OR "rss feeds" infosec TOPIC 2024 OR 2025`
- Direct source discovery: `TOPIC "research blog" OR "security blog" -site:medium.com`
- GitHub lists: `site:github.com "awesome" TOPIC security`

Collect candidate URLs. Aim for 10–20 raw candidates.

## Step 3 — Filter candidates

For each candidate:
1. Check it isn't already in feeds.xml (compare domain against Step 1 output)
2. Verify it has a discoverable RSS/Atom feed (quick HEAD or autodiscovery)
3. Note the likely feed URL

Drop candidates that fail either check.

## Step 4 — Present shortlist

For each surviving candidate, print a one-line summary:

```
1. example.com — "Short description of what this covers" — feed: https://example.com/feed
2. ...
```

Ask the user: "Which of these would you like to add? (list numbers, or 'all', or 'none')"

## Step 5 — Add selected

For each selected candidate, invoke the new-source skill inline:

Run the full new-source evaluation (Steps 1–6 of secnews:new-source) for each URL the user selected. Report each result (PASS/REJECT + folder) as you go.

Do not add feeds the user did not select.
