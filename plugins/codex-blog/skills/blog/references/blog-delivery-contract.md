# Blog Delivery Contract

This contract applies to `$blog write`, `$blog-write`, `$blog rewrite`, cluster
execution, and multilingual writing. It replaces the upstream all-or-nothing
visual preflight with a content-first, resumable delivery model.

## Hard deliverable

The only hard deliverable is a complete, factually safe SEO Markdown article.
It is complete when it has:

- accurate title, slug, meta description, one H1, and coherent H2/H3 hierarchy;
- complete introduction, body, conclusion, and any warranted FAQ;
- natural topic/keyword coverage and reader-task completion;
- traceable support for material factual claims;
- no confirmed falsehoods, TODOs, broken embeds, or generation placeholders.
- at least `max(350, floor(0.60 × requested word_count))` body words.

The advisory length target is
`max(hard floor, floor(0.85 × requested word_count))`. Falling between the hard
and advisory floors records a warning but does not withhold the Markdown.
Template length bands remain planning guidance; the normalized request target
drives these two checks.

Save this file before optional work. A reviewer score, visual count, rendering
tool, network request, external Skill, or provider credential cannot withhold it.

## Artifact layout

```text
.codex-blog/output/<slug>/
├── <slug>.md              # hard deliverable
├── review.md              # editorial findings and limitations
├── run-manifest.json      # source of truth for resumable stage state
├── schema.json            # optional
├── <slug>.html            # optional
├── <slug>.pdf             # optional
├── platform/              # optional channel formats
└── images/                # absent unless explicitly enabled
```

Do not create empty optional files or directories merely to satisfy this tree.

## Stage states

Every attempted stage records:

- `complete`: expected artifact or finding was produced;
- `degraded`: a useful partial result was produced with a stated limitation;
- `skipped`: no useful result after the allowed attempts, or the stage was not
  requested/available.

The run finishes as `complete` when requested stages finish without warnings,
or `complete_with_warnings` when the Markdown is complete and any optional stage
is degraded/skipped. Use `blocked` only when the core article remains incomplete
after three total checkpointed attempts or cannot be made factually safe.

## Retry budgets

- **Core article:** resume from its last checkpoint up to three total attempts.
  On the third incomplete attempt, stop and report the blocking diagnostic.
- **Every downstream stage:** initial attempt plus one retry, two total. Feed the
  first diagnostic into the retry. After the second failure, skip and continue.
- Never rerun a successful stage or discard an existing complete artifact.

A fact checker that proves a claim false triggers a targeted article correction,
not a generic downstream failure. Remove or correct the claim and refresh only
artifacts derived from the changed passage.

## Default no-image gate

`image_mode=deferred` is the default. Before the final image decision:

- no image, stock-search, chart, screenshot, or provider calls;
- no new `images/` directory, image frontmatter, visual placeholders, or broken
  references. A rewrite preserves pre-existing verified image references under
  the explicit exception in `blog-rewrite/SKILL.md`; it still performs no new
  visual work while deferred;
- no missing-image warnings or scoring deductions.

After the article and non-image stages complete, ask exactly once:

> The article and non-image deliverables are complete. Generate images now?

Present `No images`, `Cover only`, and `Cover plus inline images`. No answer is
equivalent to `No images` and leaves canonical `image_mode=deferred`. Map `Cover
only` to `image_mode=hero` and `Cover plus inline images` (including a bare
"yes") to `image_mode=full`. If the initial request already selected images,
run them last without asking. Full mode selects one cover and up to three inline
images, with the cover reused for Open Graph by default.

For a cluster or multilingual batch, ask once after all articles and non-image
stages, not once per article. Image work resumes from the manifest and never
rewrites article prose. Provider failure leaves the prior run complete with a
warning.

## Manifest minimum

`run-manifest.json` records:

- schema/version and run identifier;
- normalized request, selected defaults, and input provenance;
- article path, checksum when available, checkpoint, and status;
- stage name, state, attempt count, artifacts, and concise reason;
- material conflicts and fact-verification limitations;
- image mode, question state, provider/model when used, and paths;
- final status.

Never store API keys, tokens, full environment dumps, or private material in the
manifest.

## Delivery message

Lead with the Markdown path and final status. List generated optional artifacts,
then concise warnings and skipped stages. Do not make the user inspect logs to
discover a failure. Ask the image question only when the workflow reaches its
deferred-image decision and the user did not already choose.

The original all-gates delivery design came from Daniel Agrici's MIT-licensed
`claude-blog` project. This Codex contract intentionally changes the blocking
semantics to match content-first delivery.
