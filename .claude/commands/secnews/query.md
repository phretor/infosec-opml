---
model: claude-haiku-4-5-20251001
description: Search the last 30 days of cached articles for a topic or query, return a ranked reading list
---

Search recent articles across all feeds for the topic in `$ARGUMENTS`.

## Step 1 — Ensure cache is fresh

```bash
uv run python scripts/fetch_cache.py --max-age 6 2>&1 | tail -3
```

## Step 2 — Extract recent articles

```bash
python3 - << 'EOF'
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

cache = json.loads(Path(".cache/feeds.json").read_text())
cutoff = datetime.now(timezone.utc) - timedelta(days=30)
query = " ".join(sys.argv[1:]).lower()

results = []
for url, feed in cache["feeds"].items():
    for item in feed.get("items", []):
        title = item.get("title", "")
        summary = item.get("summary", "")
        text = (title + " " + summary).lower()
        if any(term in text for term in query.split()):
            results.append({
                "feed": feed["name"],
                "folder": feed["folder"],
                "title": title,
                "link": item.get("link", ""),
                "published": item.get("published", ""),
                "summary": summary[:300],
                "score": sum(text.count(term) for term in query.split()),
            })

results.sort(key=lambda x: -x["score"])
for r in results[:50]:
    print(f"[{r['score']}] {r['feed']} ({r['folder']})")
    print(f"  {r['title']}")
    print(f"  {r['link']}")
    if r["summary"]:
        print(f"  {r['summary'][:150]}")
    print()
EOF
```

Run as: `python3 - << 'EOF' ... EOF` but pass `$ARGUMENTS` as the query terms when invoking the here-doc.

## Step 3 — Rank and summarize

From the candidates above:

1. **Filter** to articles genuinely relevant to the query (title-level relevance, not just keyword noise)
2. **Group** by sub-topic if the query is broad (e.g., "LLM security" → prompt injection / model theft / supply chain)
3. **Rank** by: recency × source quality (research > news > blog)

Present as a reading list:

```
QUERY: <topic>
PERIOD: last 30 days  |  N articles found

── Sub-topic A ──────────────────────────────
1. [Source] Title
   https://...
   One sentence on why this is relevant.

2. ...

── Sub-topic B ──────────────────────────────
...
```

Cap at 20 results. If fewer than 5 results, suggest: run `/secnews:expand` for the relevant folder, or broaden the query.
