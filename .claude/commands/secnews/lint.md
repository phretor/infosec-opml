---
model: claude-haiku-4-5-20251001
description: Audit feeds.xml — find misplacements, duplicates, stale feeds, folder imbalances, and quality outliers
---

Audit feeds.xml and produce a prioritized list of recommended changes.

## Step 1 — Structural overview

```bash
uv run python -m scripts.stats
```

Note: folders with fewer than 5 feeds (sparse) or more than 80 (bloated).

## Step 2 — Duplicate detection

Key insight: the domain is not a reliable dedup key. Hosts like `feeds.feedburner.com`, `medium.com`, `substack.com`, `blogspot.com` serve many independent feeds — grouping them as "duplicates" produces false positives. A feed's identity is its **full URL**, not its host.

The script below:

1. **Normalizes URLs** — lowercases, strips trailing slashes, drops `alt`/`format` query params that yield the same feed. This catches the real duplicates (http/https variants, `?alt=rss` tacked on, trailing slash differences).
2. **Groups by host** for informational review, but **suppresses known shared-hosting proxies** from that view (otherwise the output is dominated by the 20+ unrelated feeds that happen to sit behind feedburner).

Output sections:

- `EXACT DUP` — same feed listed twice. Actionable: consolidate to one entry.
- `MULTI HOST` — multiple distinct feeds on the same host. Informational: usually legitimate topic splits (Wired, AWS, LinuxSecurity), but worth a glance.

```bash
python3 -c "
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs, urlencode
from collections import defaultdict

# Hosts where many independent feeds legitimately coexist. Excluded from the
# MULTI HOST view so it doesn't drown in per-user subdomain noise.
SHARED_HOSTS = {
    'feeds.feedburner.com', 'medium.com', 'substack.com', 'blogspot.com',
    'wordpress.com', 'reddit.com', 'github.com', 'typepad.com',
    'tumblr.com', 'beehiiv.com', 'ghost.io', 'bearblog.dev',
}

def is_shared(host):
    h = host.lower().removeprefix('www.')
    parts = h.split('.')
    for i in range(len(parts)):
        if '.'.join(parts[i:]) in SHARED_HOSTS:
            return True
    return False

def normalize(url):
    p = urlparse(url.lower().strip())
    host = p.netloc.removeprefix('www.')
    path = p.path.rstrip('/')
    qs = {k: v for k, v in parse_qs(p.query).items() if k not in ('alt', 'format')}
    query = '?' + urlencode(sorted(qs.items()), doseq=True) if qs else ''
    return f'{host}{path}{query}'

tree = ET.parse('feeds.xml')
exact = defaultdict(list)
by_host = defaultdict(list)
for folder in tree.getroot().find('body'):
    for f in folder:
        url = f.get('xmlUrl', '')
        if not url:
            continue
        entry = (f.get('text', ''), folder.get('text', ''), url)
        exact[normalize(url)].append(entry)
        host = urlparse(url.lower()).netloc.removeprefix('www.')
        by_host[host].append(entry)

dupes = [(k, v) for k, v in sorted(exact.items()) if len(v) > 1]
if dupes:
    print('=== EXACT DUP (same normalized URL — consolidate) ===')
    for key, entries in dupes:
        print(f'  {key}')
        for name, folder, url in entries:
            print(f'    [{folder}] {name} -> {url}')
    print()

multi = [(h, v) for h, v in sorted(by_host.items())
         if len(v) > 1 and not is_shared(h)]
if multi:
    print('=== MULTI HOST (multiple distinct feeds on same host — verify) ===')
    for host, entries in multi:
        print(f'  {host} ({len(entries)})')
        for name, folder, url in entries:
            print(f'    [{folder}] {name} -> {url}')
"
```

To catch duplicates *within* a shared host (e.g. the same feedburner URL added twice with subtle differences), rely on **EXACT DUP** — the URL normalization catches http/https, trailing slash, and common query-param noise. If a feed on a shared host appears once with its proxy URL and once with its canonical URL (e.g. `feeds.feedburner.com/X` vs `x.com/feed`), those won't match automatically; surface them during manual review of the corresponding folder.

## Step 3 — Staleness check (cache-based)

```bash
python3 -c "
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

cache_path = Path('.cache/feeds.json')
if not cache_path.exists():
    print('No cache. Run: uv run python scripts/fetch_cache.py')
    exit()

cache = json.loads(cache_path.read_text())
cutoff = datetime.now(timezone.utc) - timedelta(days=90)

for url, data in sorted(cache['feeds'].items(), key=lambda x: x[1].get('name','')):
    items = data.get('items', [])
    if not items:
        print(f'NO_ARTICLES [{data[\"folder\"]}] {data[\"name\"]}')
        continue
    last_pub = items[0].get('published', '')
    if last_pub:
        try:
            # rough date check by year
            year = int(last_pub[-4:]) if len(last_pub) >= 4 else 0
            if year < 2024:
                print(f'STALE({year}) [{data[\"folder\"]}] {data[\"name\"]} -> {url}')
        except Exception:
            pass
" 2>/dev/null || echo "(cache not available — staleness check skipped)"
```

## Step 4 — Misplacement sampling

For each folder, fetch 3 random feeds and run the classify-feeds logic (fetch 3 articles, classify). Flag any whose suggested folder differs from current.

```bash
python3 -c "
import xml.etree.ElementTree as ET, random
tree = ET.parse('feeds.xml')
sample = []
for folder in tree.getroot().find('body'):
    feeds = [f for f in folder if f.get('type') == 'rss']
    for f in random.sample(feeds, min(3, len(feeds))):
        sample.append((folder.get('text',''), f.get('text',''), f.get('xmlUrl','')))
for folder, name, url in sample:
    print(folder, '|', name, '|', url)
" | head -60
```

For each sampled feed, fetch its 3 recent articles (reuse `/tmp/parse_feed.py`) and classify. Flag mismatches.

## Step 5 — Synthesize

Produce a prioritized change list in three sections:

### High priority
- Duplicate feeds to consolidate (keep best URL, remove other)
- Clear misplacements (high-confidence folder change)
- Feeds with no articles / errors for 90+ days → candidates for `check_feeds --remove`

### Medium priority
- Likely misplacements (medium-confidence)
- Folders that are sparse or bloated with suggestions

### Low priority
- Quality outliers: feeds that look like pure marketing, pure reposts, or off-topic
- HTTP feeds with HTTPS equivalents available

Do not modify feeds.xml. Present the list and ask the user which items to act on.
