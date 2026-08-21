---
name: blog-cluster
description: >
  Plan and execute semantic hub-and-spoke blog clusters from a seed keyword or
  imported strategy. Use for `$blog cluster`; produces a keyword/intent plan,
  complete interlinked SEO articles through `$blog-write`, a resumable
  scorecard, and optional visuals only after the batch is complete.
license: MIT
metadata:
  author: AgriciDaniel
  version: "2.1.2"
  category: blog
---

# Blog Cluster

Build a pillar-and-spoke content system using SERP overlap, intent, entities,
unique keyword targets, and planned reciprocal links. The complete Markdown
article is the hard deliverable for each post; batch analysis, schema, maps,
rendering, and images are non-blocking.

> Design credit: Lutfiya Miller's MIT-licensed `semantic-cluster-engine`.
> Codex Blog ports Daniel Agrici's MIT-licensed claude-blog 2.1.1 integration;
> the preserved source, license, and change record are in `THIRD_PARTY.md`.

## Commands

| Invocation | Result |
|---|---|
| `$blog cluster plan <seed>` | Create a validated cluster plan |
| `$blog cluster plan --from strategy <path>` | Normalize an existing Blog strategy |
| `$blog cluster execute <cluster-plan.json>` | Write/resume all planned articles |
| `$blog cluster status <plan-or-manifest>` | Show queue and artifact states |

If `$blog cluster` is otherwise ambiguous, ask whether the user wants plan or
execute. Planning never auto-executes unless explicitly requested.

Use the bundled runtime for execution state; do not invent or edit batch state
by hand:

```bash
codex-blog cluster prepare <cluster-plan.json>
codex-blog cluster status --run <cluster-output-directory>
codex-blog cluster finalize --run <cluster-output-directory>
codex-blog cluster decline-images --run <cluster-output-directory>
```

An image request made up front is `cluster prepare ... --images hero|full`.
After the deferred batch question, approval is
`cluster finalize ... --images hero|full`. Both choices are only planned after
every article has reached a terminal core/non-image state. `images_planned` is
the handoff into generation, not the end of an approved image run: immediately
process each successful article through `$blog-image` in native Codex,
configured API, then MCP fallback order, attach the result, and refresh only
image-sensitive outputs. A blocked article is reported and skipped.

Load `references/semantic-clustering.md` for SERP grouping,
`references/cluster-architecture.md` for links, and
`references/execution-workflow.md` for the context/manifest contract.

## Plan

1. Expand the seed using Codex web search or imported keyword data. Capture
   related questions, modifiers, named entities, and observed SERP results.
2. Group phrases primarily by shared result URLs and reader intent, then by
   semantic proximity. Four or more shared top-ten URLs is a useful same-intent
   signal, not an immutable rule.
3. Choose one broad pillar and 2-15 distinct spokes appropriate to the topic.
   Every page gets one unique primary keyword, supporting terms, intent,
   template, target depth, differentiation, and cluster role.
4. Build reciprocal pillar/spoke and contextual sibling links. Because all
   slugs are known at planning time, use final planned relative paths; never put
   unresolved `[INTERNAL-LINK]` markers into publishable articles.
5. Write `.codex-blog/output/clusters/<seed-slug>/cluster-plan.json`. Preserve
   imported values and report conflicts rather than silently overriding them.

Relative demand labels such as high/medium/low may summarize observed evidence,
but never present them as measured search volume. Use exact volume only from a
named dataset/provider with date, market, and metric semantics.

The optional interactive SVG/HTML cluster map is a visual artifact. Do not
produce it in the default plan. Generate it only when visuals were explicitly
requested, after the non-image plan/report is complete, with escaped labels, no
scripts/event handlers, and accessible SVG titles/descriptions.

## Plan schema

The JSON records `seed_keyword`, `generated_at`, `language`, `locale`, planned
base path, pillar, clusters/posts, link matrix, execution order, and provenance.
Each page records stable ID, title, slug/path, primary/secondary keywords,
intent, entities, template, target-depth guidance, differentiation, links to/from,
and optional upstream SEO/material references. See the execution reference for
the normalized cluster context passed to `$blog-write`.

Validate unique IDs/slugs/primary keywords, valid link targets, no path escape,
and one pillar. Cannibalization in the plan blocks execution until targets are
made distinct; missing volume, visual map, or external SEO provider does not.

## Execute

1. Resolve one explicit `cluster-plan.json`, validate it, and create/update the
   batch manifest inside its cluster output directory.
2. Write the pillar first, then spokes in declared dependency/priority order.
   Independent spokes may run in bounded parallel groups.
3. For every page, pass the full cluster context plus any SEO brief/material
   packet to `$blog-write`. Skip clarification and outline approval because the
   plan supplies them. Set `image_mode=deferred` unless the initial user request
   explicitly selected images.
4. `$blog-write` saves a complete article and handles up to three total core
   attempts with checkpoint resume. A failed article is recorded as `blocked`;
   preserve it and continue
   with other independent pages. Do not let a reviewer score or optional stage
   stop the batch.
5. Insert/validate real relative links using planned slugs. Add cluster metadata
   to frontmatter. Never replace prose broadly or inject a dangling link.
6. Attempt per-post and cluster-level non-image checks (SEO, schema, analysis,
   cannibalization, link audit, scorecard) with an initial attempt and one retry
   each. Then skip/warn and continue.
7. Write `cluster-scorecard.md` and the batch `run-manifest.json` with article,
   link, check, failure, and resume states.

On resume, use manifests and existing complete article files; do not rewrite
them. Retry only blocked/incomplete articles or explicitly selected downstream
stages. A filesystem failure for the cluster directory stops new writes but does
not remove existing files.

## Batch image policy

Do not discover image providers, create maps/charts, generate per-post Hero
images, or add image placeholders during planning/writing/non-image checks.

After all possible articles and non-image stages finish, ask once for the whole
batch: **"The cluster articles and non-image deliverables are complete. Generate
images now?"** Offer no images, covers only, or covers plus inline images. No
reply means no images. If the initial request already chose images, run them now
without asking. Use `$blog-image` per selected article, resume from manifests,
and treat provider failures as warnings.

## Scorecard

Report per page: complete/blocked state, file path, target, template, links,
optional stage states, and warnings. Summarize link reciprocity, orphan pages,
intent/template diversity, keyword conflicts, uncovered targets, and suggested
next actions. Visual absence is not a warning when images are deferred.

## Independence

Codex Blog performs clustering and writing itself. Codex SEO briefs/cluster
outputs and `extract-seo-materials` packages are optional inputs through
`skills/blog/references/input-contract.md`; never import their source or require
their installation. If Codex web search is unavailable, build a provisional plan
from supplied data and label the missing SERP validation.
