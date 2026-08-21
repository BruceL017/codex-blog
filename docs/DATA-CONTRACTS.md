# Data contracts

Codex Blog accepts ordinary Markdown and JSON, then normalizes them into two
stable internal contracts. JSON examples are illustrative; unknown fields are
ignored instead of being interpreted as instructions.

## SEOContentPacket v1

```json
{
  "schema_version": 1,
  "topic": "AI content pipeline",
  "primary_keyword": "AI content pipeline",
  "secondary_keywords": ["SEO content workflow"],
  "search_intent": "informational",
  "audience": "content teams",
  "language": "en",
  "template": "tutorial",
  "word_count": 2200,
  "outline": ["What the pipeline does", "Implementation"],
  "content_gaps": ["No competitor explains failure recovery"],
  "information_gain": ["Include a resumable manifest example"],
  "internal_links": [{"url": "/seo-brief", "anchor": "SEO brief"}],
  "competitor_urls": [],
  "materials": [],
  "sources": [],
  "cluster_context": {},
  "provenance": []
}
```

## BlogWriteRequest v1

`BlogWriteRequest` contains the packet fields plus `site_context`,
`brand_voice`, `conflicts`, and `image_mode`. Supported image modes are:

- `deferred`: default; do not inspect or call providers;
- `hero`: create a cover only after non-image completion;
- `full`: create a cover and up to three useful inline images after completion.

The default word-count target is 2200 when no more relevant target is supplied.
Word count guides structure and never justifies filler, but the hard completeness
gate does enforce a minimum visible length. The article must contain at least
`max(350, floor(word_count × 0.60))` visible word units. Reaching less than
`max(hard_floor, floor(word_count × 0.85))` produces an advisory warning after
the hard gate passes. Latin word tokens and individual CJK characters count as
visible units; fenced code, inline code, and URLs do not.

## Material item

```json
{
  "title": "Checkpoint recovery",
  "text": "The draft can resume from its last completed section.",
  "fact_state": "engineering",
  "source_refs": ["session:abc#turn-12"],
  "public_boundary": "publishable",
  "maturity": "implemented",
  "contribution_types": ["mechanism", "differentiator"]
}
```

`hypothesis`, `failed`, and `unknown` material must not be presented as a
verified public fact. Restricted or confirmation-required material must remain
out of the publication body until explicitly cleared.

## Run manifest

`run-manifest.json` records run identity, normalized request and article paths,
request/article digests, language, template, provenance, conflicts, image mode,
image status, the once-only image decision, warnings, timestamps, and every
stage. A stage contains its status, attempts, artifacts, warning, and error.

Valid stage states are `pending`, `complete`, `degraded`, `skipped`, and
`blocked`. Downstream work is capped at two total attempts. Core generation may
resume three times because a complete article is the hard requirement.

## Adapter commands

Inspect an adapter without drafting:

```bash
codex-blog adapter brief ./seo-brief.json
codex-blog adapter cluster ./cluster-plan.json --post pillar-page
codex-blog adapter materials ./_content_materials/sessions/project-seo-materials.md
```

The commands emit normalized data or an explicit parse error. They never invoke
the external Skill that may have created the file.
