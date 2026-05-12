---
description: Identify the top 10 most-discussed topics across all sources in the last 30 days, write a brief + RSS feed to hot/
---

Survey all feeds for the past 30 days, cluster coverage by topic, and produce a Kagi-style news brief.

## Step 1 — Refresh cache

```bash
uv run python scripts/fetch_cache.py --max-age 6 2>&1 | tail -3
```

## Step 2 — Extract article titles + summaries (last 30 days)

```bash
python3 - << 'EOF'
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

cache = json.loads(Path(".cache/feeds.json").read_text())
cutoff = datetime.now(timezone.utc) - timedelta(days=30)

articles = []
for url, feed in cache["feeds"].items():
    for item in feed.get("items", []):
        articles.append(
            f"[{feed['folder']}] {feed['name']}: {item['title']} | {item['summary'][:120]}"
        )

# Print in batches of 500 lines to avoid context overflow
for i, line in enumerate(articles):
    print(line)
    if i >= 2000:
        print(f"… ({len(articles) - 2001} more articles truncated)")
        break
EOF
```

## Step 3 — Identify top 10 topics (batched if needed)

Read the article list in batches of ~500 lines. For each batch, extract recurring themes — not individual stories, but topics that multiple sources covered. Keep a running tally.

After all batches, consolidate into the **top 10 topics** ranked by number of distinct sources that covered them. A topic qualifies if at least 3 sources touched it.

For each topic record:
- Short title (5–8 words)
- Source count (how many feeds covered it)
- Top 5 representative article links
- Which folders contributed

## Step 4 — Write the brief

For each of the 10 topics, write a 3–4 sentence summary that:
- States what happened or what the trend is
- Names the key actors, CVEs, tools, or organizations involved
- Notes the security significance
- Cites 2–3 sources by name

## Step 5 — Write output files

**hot/YYYY-MM-DD.md** (use today's date):

```markdown
# Security Hot Topics — YYYY-MM-DD

> 30-day survey across NNN feeds · top 10 topics by coverage breadth

## 1. Topic Title
*N sources · folders: ...*

Summary paragraph.

**Sources:** [Feed Name](url) · [Feed Name](url) · ...

---

## 2. ...
```

**hot/hot.xml** — RSS 2.0 feed, one `<item>` per topic:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Security Hot Topics</title>
    <link>https://github.com/phretor/infosec-opml</link>
    <description>Top 10 security topics from the last 30 days</description>
    <lastBuildDate>RFC-822 DATE</lastBuildDate>
    <item>
      <title>Topic Title (N sources)</title>
      <description>Summary paragraph. Sources: Feed1, Feed2, Feed3.</description>
      <link>FIRST_ARTICLE_URL</link>
      <pubDate>RFC-822 DATE</pubDate>
      <guid>hot-YYYYMMDD-1</guid>
    </item>
    <!-- repeat for each topic -->
  </channel>
</rss>
```

Write both files using the Write tool. Then print a one-line summary per topic to confirm.
