---
name: blog-data
description: >
  Import and analyze optional search, analytics, performance, entity, video, and
  keyword data for blog decisions. Use for `$blog data`, GSC/GA4/CrUX/PageSpeed
  workflows, exported datasets, or configured provider APIs; unavailable data
  never blocks Blog writing.
license: MIT
metadata:
  author: AgriciDaniel
  codex-port: BruceL017
  version: "2.1.2"
---

# Blog Data

Add measured performance and search evidence to Blog workflows without making
one provider a core dependency. Prefer user-provided exports when they answer the
question. Use bundled Google API helpers or other configured APIs only when
credentials already exist and the requested task benefits from live data.

## Commands

| Invocation | Purpose |
|---|---|
| `$blog data import <file>` | Normalize CSV/JSON exports |
| `$blog data pagespeed <url>` | PageSpeed lab data and available CrUX field data |
| `$blog data crux <origin-or-url>` | Current/history Core Web Vitals |
| `$blog data gsc <args>` | Search Console queries and index inspection |
| `$blog data ga4 <args>` | Organic traffic and landing-page reports |
| `$blog data keywords <args>` | Configured keyword-provider data |
| `$blog data entities <file-or-url>` | Entity extraction/analysis |
| `$blog data video <query>` | Configured video search |
| `$blog data doctor` | Report capability tiers and missing configuration |

The existing Google helpers under `skills/blog-data/scripts/` are optional. Run
them through `codex-blog run blog-data/run.py <script-name> [arguments]`; never
execute a same-named project-local script. Other provider results enter through
the same normalized record and need not emulate Google endpoints.

## Normalized record

For every metric or row retain:

- provider and property/account scope;
- query/filter and date range;
- dimensions, metric name, value, unit, and aggregation semantics;
- collection timestamp, freshness/lag, sampling or incompleteness flags;
- source file/API operation and any known limitations.

Do not sum partial GSC rows as site totals, present lab PageSpeed data as field
data, infer search volume from SERP prominence, or compare mismatched periods.
Keep provider-specific fields in an extensions object rather than discarding
them.

## Credentials and failure

Read credentials from documented environment variables or configured secret
stores only. Never print tokens, client secrets, service-account content, or full
environment dumps. Do not initiate authentication, enable billing, request an
indexing mutation, or install optional SDKs without explicit user authorization.

Missing credentials, quota exhaustion, insufficient traffic, stale exports, and
provider outages produce `degraded` or `skipped` data stages. Return what is
available with limitations. `$blog-write` remains fully functional using its
native research and supplied material.

## Writing integration

Pass only relevant, interpretable findings into a Blog brief or
`SEOContentPacket`. Performance data may refine priority, intent, decay, and
internal linking, but it cannot dictate unsupported claims. Cite public data in
the article only when the underlying source is publicly retrievable or the user
explicitly authorizes publication of first-party results.
