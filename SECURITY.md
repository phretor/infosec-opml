# Security Policy

## Scope

This policy covers two kinds of security concerns:

1. **Repository and workflow security** — credential exposure, workflow misconfigurations, supply-
   chain issues in the sync pipeline, or any defect that could let an attacker influence what lands
   in `feeds.xml`
2. **Malicious feeds** — a feed currently listed in `feeds.xml` that has started distributing
   malware, phishing, C2 traffic, or similar hostile content

Non-security issues (dead feeds, miscategorized feeds, wrong metadata) belong in a
[bug report](../../issues/new?template=bug_report.yml), not here.

## Reporting

Please use **[GitHub Private Security Advisories](../../security/advisories/new)**. This gives us a
private thread to triage and, where appropriate, request a CVE.

Please include:

- The feed URL or workflow component in question
- Observed behavior (sample URL, response, timeline)
- Any supporting evidence (headers, hashes, screenshots)

We aim to acknowledge new reports within one week. Response times beyond that are best-effort —
this is a maintained-by-one-person repository.

## What happens after a report

- For malicious feeds, the feed will typically be removed from the upstream Miniflux instance,
  which will propagate into `feeds.xml` on the next scheduled sync
- For repository/workflow issues, a fix lands via a normal commit (and a CVE where appropriate)

## Scope notes

This repository publishes a list of third-party RSS/Atom URLs. The content of those feeds is not
under our control; please report feed-content concerns to the publisher directly whenever possible,
and use this channel for cases where the feed is being distributed from here as if trustworthy.
