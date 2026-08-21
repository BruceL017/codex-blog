# Cluster Execution Workflow

Load this reference during `$blog cluster execute`.

Create or resume the queue with
`codex-blog cluster prepare <cluster-plan.json>`, inspect it with
`codex-blog cluster status --run <cluster-output-directory>`, and finalize every
ready article with `codex-blog cluster finalize --run <cluster-output-directory>`.
The runtime persists the one batch-level image decision; use
`cluster decline-images` for no images or repeat `cluster finalize` with
`--images hero|full` after approval.

## Queue

Write the pillar first so every spoke has a stable hub path. Then follow explicit
dependencies and cluster priority; bounded parallel execution is allowed for
independent spokes. The plan owns all final slugs before writing starts.

## Context passed to `$blog-write`

```text
CLUSTER: <seed/topic>
ROLE: pillar | spoke
GROUP: <cluster name>
POSITION: <n>/<total>
PRIMARY KEYWORD: <value>
SECONDARY KEYWORDS: <values>
SEARCH INTENT: <value>
TEMPLATE: <value>
TARGET DEPTH: <guidance, not a gate>
DIFFERENTIATION: <page-specific gap>
PLANNED PATH: <relative path>
LINKS: <target path, anchor guidance, required/contextual>
SIBLINGS: <IDs, titles, paths, primary targets>
SEO BRIEF/MATERIAL REFS: <paths or inline normalized packet>
IMAGE MODE: deferred | hero | full
```

Also instruct the writer to run autonomously from these resolved parameters,
preserve provenance/publication boundaries, remove unverifiable numeric claims,
save complete Markdown first, and never emit visual/internal-link placeholders.

## Frontmatter

Add project-compatible equivalents of:

```yaml
cluster: "<seed>"
clusterRole: "pillar|spoke"
clusterGroup: "<group>"
clusterPosition: "<n>/<total>"
```

## Link pass

All destinations use planned paths, so links may be written before destination
files exist. After each batch wave, verify destination IDs/paths against the
plan. A missing/blocked destination becomes a scorecard warning; remove a link
that would be broken in the publication batch or leave it only in the editorial
link plan, never as a generation marker.

## Failure and resume

| Scenario | Behavior |
|---|---|
| Core article incomplete | Let `$blog-write` resume up to three total attempts; mark blocked and continue independent pages |
| Optional per-post stage fails | Retry once, then skip/warn |
| User interrupts | Save batch/article manifests; resume only unfinished states |
| Filesystem write fails | Stop new writes, preserve artifacts, report exact path/error |
| Visual provider fails | Preserve articles, mark image stage skipped, continue |

For each page, use the normalized request target: fewer than
`max(350, floor(0.60 × requested word_count))` body words is an incomplete core
article; `max(hard floor, floor(0.85 × requested word_count))` is advisory and
missing it produces only a warning. A reviewer score is never a core failure.

## Batch scorecard

Include summary, per-post states/paths, primary targets, link in/out counts,
orphan/broken destinations, intent/template diversity, keyword conflicts,
optional-stage states/attempts, missing evidence, and next actions. Image fields
are `N/A` with no warning in deferred mode.

## Images

No per-post image work occurs in the main queue. Finish the scorecard and all
non-image stages, then follow the one-question batch image policy in the parent
Skill. If approved, generate selected assets last and update only affected
manifests, Markdown image metadata/references, schema, and renders.
