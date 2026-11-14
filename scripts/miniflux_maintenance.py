"""One-time, explicitly approved Miniflux feed repair; dry run by default.

The fixed URLs are permanent moves and conclusive deletions rechecked on
2026-11-14. One entry missing from Miniflux, duplicated there, or aimed at a
URL already subscribed blocks the whole plan; dry-run names those blocking
entries and apply mutates nothing until they are gone. No OPML edits are made
here: Miniflux is the source of truth.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Literal

import httpx

HTTP_TIMEOUT = 30.0

Action = Literal["repoint", "delete"]


@dataclass(frozen=True)
class Repair:
    action: Action
    old: str
    reason: str
    new: str | None = None


# Rechecked 2026-11-14. Each repoint target returned HTTP 200 and parsed as RSS or Atom.
# Omitted leads were not well-formed XML, or were a 403, a 302, or no longer a redirect.
REPAIRS = (
    Repair(
        "repoint",
        "https://cyber.gc.ca/webservice/en/rss/alerts",
        "301 to https://www.cyber.gc.ca/api/cccs/atom/v1/get"
        "?feed=alerts_advisories&lang=en; target 200 Atom",
        "https://www.cyber.gc.ca/api/cccs/atom/v1/get?feed=alerts_advisories&lang=en",
    ),
    Repair(
        "repoint",
        "https://www.cisa.gov/uscert/ncas/all.xml",
        "301 to https://www.cisa.gov/cybersecurity-advisories/all.xml; target 200 RSS",
        "https://www.cisa.gov/cybersecurity-advisories/all.xml",
    ),
    Repair(
        "repoint",
        "https://cve.threatint.com/rss/new",
        "301 to https://cve.threatint.com/rss/new.rss; target 200 RSS",
        "https://cve.threatint.com/rss/new.rss",
    ),
    Repair(
        "repoint",
        "https://www.kyberturvallisuuskeskus.fi/sites/default/files/rss/vulns.xml",
        "301 to https://www.kyberturvallisuuskeskus.fi/files/rss/vulns.xml; target 200 RSS",
        "https://www.kyberturvallisuuskeskus.fi/files/rss/vulns.xml",
    ),
    Repair(
        "repoint",
        "https://usn.ubuntu.com/rss.xml",
        "301 to https://ubuntu.com/security/notices/rss.xml; target 200 RSS",
        "https://ubuntu.com/security/notices/rss.xml",
    ),
    Repair(
        "repoint",
        "https://7ms.us/rss/",
        "301 to https://7minsec.com/feed/; target 200 RSS",
        "https://7minsec.com/feed/",
    ),
    Repair(
        "repoint",
        "https://badcyber.com/feed",
        "301 to https://badcyber.com/feed.xml; target 200 RSS",
        "https://badcyber.com/feed.xml",
    ),
    Repair(
        "repoint",
        "https://jacknaglieri.substack.com/feed",
        "301 to https://www.detectionatscale.com/feed; target 200 RSS",
        "https://www.detectionatscale.com/feed",
    ),
    Repair(
        "repoint",
        "https://malicious.life/feed/podcast/",
        "301 to https://feeds.redcircle.com/597cfd00-b29a-49c6-9622-03c8decfc35f; target 200 RSS",
        "https://feeds.redcircle.com/597cfd00-b29a-49c6-9622-03c8decfc35f",
    ),
    Repair(
        "repoint",
        "https://www.smashingsecurity.com/rss",
        "301 to https://feeds.redcircle.com/c478d684-038f-4b13-8507-bc32af486a2c; target 200 RSS",
        "https://feeds.redcircle.com/c478d684-038f-4b13-8507-bc32af486a2c",
    ),
    Repair(
        "repoint",
        "https://tldrsec.com/feed.xml",
        "301 to https://rss.beehiiv.com/feeds/xgTKUmMmUm.xml; target 200 RSS",
        "https://rss.beehiiv.com/feeds/xgTKUmMmUm.xml",
    ),
    Repair(
        "repoint",
        "https://bunniestudios.com/feed",
        "301 to https://www.bunniestudios.com/feed/; target 200 RSS (www canonical)",
        "https://www.bunniestudios.com/feed/",
    ),
    Repair(
        "repoint",
        "https://shielder.com/blog/feed/",
        "301 to https://www.shielder.com/blog/index.xml; target 200 RSS",
        "https://www.shielder.com/blog/index.xml",
    ),
    Repair(
        "repoint",
        "https://samcurry.net/feed.rss",
        "308 to https://samcurry.net/api/feed.rss; target 200 RSS",
        "https://samcurry.net/api/feed.rss",
    ),
    Repair(
        "repoint",
        "https://blog.securitybreached.org/feed",
        "308 to https://blog.securitybreached.org/rss.xml; target 200 RSS",
        "https://blog.securitybreached.org/rss.xml",
    ),
    Repair(
        "repoint",
        "https://www.trustedsec.com/feed/",
        "301 to https://www.trustedsec.com/feed.rss; target 200 RSS",
        "https://www.trustedsec.com/feed.rss",
    ),
    Repair(
        "repoint",
        "https://blog.sonatype.com/rss.xml",
        "301 to https://www.sonatype.com/blog/rss.xml; target 200 RSS",
        "https://www.sonatype.com/blog/rss.xml",
    ),
    Repair(
        "repoint",
        "https://blog.chainalysis.com/feed/",
        "301 to https://www.chainalysis.com/feed/; target 200 RSS",
        "https://www.chainalysis.com/feed/",
    ),
    Repair(
        "repoint",
        "https://intel471.com/blog/feed",
        "301 to https://www.intel471.com/blog/feed; target 200 RSS (www canonical)",
        "https://www.intel471.com/blog/feed",
    ),
    Repair(
        "repoint",
        "https://blog.malwarebytes.org/feed/",
        "301 to https://www.malwarebytes.com/blog/feed/index.xml; target 200 RSS",
        "https://www.malwarebytes.com/blog/feed/index.xml",
    ),
    Repair(
        "repoint",
        "https://www.cert.pl/en/feed/",
        "301 to https://cert.pl/en/rss.xml; target 200 RSS",
        "https://cert.pl/en/rss.xml",
    ),
    Repair(
        "repoint",
        "https://cert.at/cert-at.en.blog.rss_2.0.xml",
        "301 to https://www.cert.at/cert-at.en.blog.rss_2.0.xml; target 200 RSS (www canonical)",
        "https://www.cert.at/cert-at.en.blog.rss_2.0.xml",
    ),
    Repair(
        "repoint",
        "https://cloudsecurityalliance.org/blog/feed/",
        "301 to https://cloudsecurityalliance.org/feed/; target 200 RSS",
        "https://cloudsecurityalliance.org/feed/",
    ),
    Repair(
        "repoint",
        "https://cyber.gc.ca/webservice/en/rss/news",
        "301 to https://www.cyber.gc.ca/api/cccs/atom/v1/get"
        "?feed=news_events_guidance&lang=en; target 200 Atom",
        "https://www.cyber.gc.ca/api/cccs/atom/v1/get?feed=news_events_guidance&lang=en",
    ),
    Repair(
        "repoint",
        "https://www.kyberturvallisuuskeskus.fi/sites/default/files/rss/news.xml",
        "301 to https://www.kyberturvallisuuskeskus.fi/files/rss/news.xml; target 200 RSS",
        "https://www.kyberturvallisuuskeskus.fi/files/rss/news.xml",
    ),
    Repair(
        "repoint",
        "https://www.ria.ee/en/news-feed/all/feed",
        "301 to https://www.ria.ee/en/rss-feeds/rss.xml; target 200 RSS",
        "https://www.ria.ee/en/rss-feeds/rss.xml",
    ),
    Repair(
        "repoint",
        "https://labs.ripe.net/RSS",
        "301 to https://labs.ripe.net/feed.xml; target 200 RSS",
        "https://labs.ripe.net/feed.xml",
    ),
    Repair(
        "repoint",
        "https://proton.me/blog/feed",
        "301 to https://proton.me/blog/feed.xml; target 200 RSS",
        "https://proton.me/blog/feed.xml",
    ),
    Repair(
        "repoint",
        "https://www.cyberscoop.com/feed/",
        "301 to https://cyberscoop.com/feed/; target 200 RSS (www canonical)",
        "https://cyberscoop.com/feed/",
    ),
    Repair(
        "delete",
        "https://www.zdnet.com/blog/security/rss.xml",
        "duplicate ZDNet security URL; both 301 to general https://www.zdnet.com/rss/news/",
    ),
    Repair(
        "repoint",
        "https://www.zdnet.com/topic/security/rss.xml",
        "subscribed URL 301s to general https://www.zdnet.com/rss/news/; security feed 200 Atom",
        "https://www.zdnet.com/rss/security/",
    ),
    Repair(
        "repoint",
        "https://www.europol.europa.eu/rss.xml",
        "301 to https://www.europol.europa.eu/cms/api/rss/news; target 200 RSS",
        "https://www.europol.europa.eu/cms/api/rss/news",
    ),
    Repair(
        "repoint",
        "https://www.theregister.co.uk/security/headlines.atom",
        "301 to https://www.theregister.com/security/headlines.atom; followed redirects 200 RSS",
        "https://www.theregister.com/security/headlines.atom",
    ),
    Repair(
        "repoint",
        "https://diablohorn.com/rss/",
        "301 to https://diablohorn.com/feed/; target 200 RSS",
        "https://diablohorn.com/feed/",
    ),
    Repair(
        "repoint",
        "https://www.grahamcluley.com/feed/",
        "301 to https://grahamcluley.com/feed/; target 200 RSS (www canonical)",
        "https://grahamcluley.com/feed/",
    ),
    Repair(
        "repoint",
        "https://www.j4vv4d.com/feed/",
        "301 to https://javvadmalik.com/feed/; target 200 RSS",
        "https://javvadmalik.com/feed/",
    ),
    Repair(
        "repoint",
        "https://www.schneier.com/blog/atom.xml",
        "301 to https://www.schneier.com/feed/atom/; target 200 Atom",
        "https://www.schneier.com/feed/atom/",
    ),
    Repair(
        "repoint",
        "https://feeds.bloomberg.com/technology/news.rss",
        "301 to https://www.bloomberg.com/feeds/technology/news.rss; target 200 RSS",
        "https://www.bloomberg.com/feeds/technology/news.rss",
    ),
    Repair(
        "repoint",
        "https://lambda.ai/blog/rss.xml",
        "301 to https://lambda.com/blog/rss.xml; target 200 RSS",
        "https://lambda.com/blog/rss.xml",
    ),
    Repair(
        "repoint",
        "https://www.vice.com/en/rss",
        "301 to https://www.vice.com/en/feed/; target 200 RSS",
        "https://www.vice.com/en/feed/",
    ),
    Repair(
        "repoint",
        "https://gizmodo.com/rss",
        "301 to https://gizmodo.com/feed; target 200 RSS",
        "https://gizmodo.com/feed",
    ),
    Repair(
        "repoint",
        "https://www.macrumors.com/macrumors.xml",
        "301 to https://feeds.macrumors.com/MacRumors-Front; target 200 RSS",
        "https://feeds.macrumors.com/MacRumors-Front",
    ),
    Repair(
        "repoint",
        "https://techblog.netflix.com/feeds/posts/default",
        "301 to https://medium.com/feed/netflix-techblog; target 200 RSS",
        "https://medium.com/feed/netflix-techblog",
    ),
    Repair(
        "repoint",
        "https://www.loopinsight.com/feed/",
        "301 to https://loopinsight.com/feed/; target 200 RSS (www canonical)",
        "https://loopinsight.com/feed/",
    ),
    Repair(
        "repoint",
        "https://blog.ubuntu.com/feed",
        "301 to https://ubuntu.com/blog/feed; target 200 RSS",
        "https://ubuntu.com/blog/feed",
    ),
    Repair(
        "repoint",
        "https://flyingpenguin.com/feed",
        "301 to https://www.flyingpenguin.com/feed/; target 200 RSS (www canonical)",
        "https://www.flyingpenguin.com/feed/",
    ),
    Repair(
        "repoint",
        "https://scarletink.com/feed",
        "301 to https://www.scarletink.com/rss/; target 200 RSS",
        "https://www.scarletink.com/rss/",
    ),
    Repair(
        "delete",
        "https://blog.fox-it.com/feed/",
        "404 on an NCC Group page; no replacement feed found",
    ),
    Repair(
        "delete",
        "https://blog.convisoappsec.com/feed/",
        "301 to https://www.convisoappsec.com/posts/feed then 404; no replacement feed found",
    ),
)


def _block_reason(repair: Repair, by_url: dict[str, list[int]]) -> str | None:
    """Why this entry would make an apply unsafe, or None when it is ready."""
    ids = by_url.get(repair.old, [])
    if not ids:
        return "missing from Miniflux"
    if len(ids) != 1:
        return "ambiguous URL"
    if repair.new is not None and repair.new in by_url:
        return "replacement already subscribed"
    return None


def run(client: httpx.Client, base_url: str, token: str, *, apply: bool = False) -> int:
    """List every planned action; reject incomplete/ambiguous state before any writes."""
    base = base_url.rstrip("/") + "/v1/feeds"
    headers = {"X-Auth-Token": token}
    response = client.get(base, headers=headers)
    response.raise_for_status()
    by_url: dict[str, list[int]] = {}
    for feed in response.json():
        by_url.setdefault(feed["feed_url"], []).append(feed["id"])

    blockers = {
        repair.old: reason
        for repair in REPAIRS
        if (reason := _block_reason(repair, by_url)) is not None
    }

    counts = {"repoint": 0, "delete": 0, "skip": 0, "failed": 0}
    for repair in REPAIRS:
        target = f" -> {repair.new}" if repair.new else ""
        block = blockers.get(repair.old)
        if block or blockers:
            detail = f"blocking: {block}" if block else "plan incomplete; no mutations"
            print(f"skip {repair.old}{target} | {detail}; {repair.reason}")
            counts["skip"] += 1
            continue
        if apply:
            url = f"{base}/{by_url[repair.old][0]}"
            try:
                if repair.action == "repoint":
                    result = client.put(url, headers=headers, json={"feed_url": repair.new})
                else:
                    result = client.delete(url, headers=headers)
                result.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"skip {repair.old}{target} | API failure: {exc}; {repair.reason}")
                counts["failed"] += 1
                continue
        print(f"{repair.action} {repair.old}{target} | {repair.reason}")
        counts[repair.action] += 1
    if blockers:
        listed = "; ".join(f"{url} ({why})" for url, why in blockers.items())
        print(f"Blocking: {listed}. Apply will mutate nothing.")
    mode = "apply" if apply else "dry-run"
    print(
        f"Summary ({mode}): repoint={counts['repoint']} delete={counts['delete']} "
        f"skip={counts['skip']} failed={counts['failed']}"
    )
    return 1 if counts["skip"] or counts["failed"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="List actions without changing Miniflux (default)"
    )
    mode.add_argument(
        "--apply", action="store_true", help="Apply the listed actions after approval"
    )
    args = parser.parse_args()
    base = os.environ.get("MINIFLUX_URL")
    token = os.environ.get("MINIFLUX_TOKEN")
    if not base or not token:
        parser.error("MINIFLUX_URL and MINIFLUX_TOKEN must be set")
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            result = run(client, base, token, apply=args.apply)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        print(f"Miniflux maintenance failed: {exc}", file=sys.stderr)
        sys.exit(1)
    sys.exit(result)


if __name__ == "__main__":
    main()
