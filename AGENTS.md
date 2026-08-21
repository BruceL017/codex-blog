# Repository instructions for coding agents

## Product invariants

- The complete SEO Markdown article is the only hard delivery requirement.
- Default image mode is `deferred`. Do not call, probe, or configure an image
  provider until the article and non-image stages finish and the user opts in.
- A downstream stage receives one retry (two total attempts), then becomes
  `degraded` or `skipped`; it must not block an already complete article.
- Codex SEO and `extract-seo-materials` are optional data adapters. The core must
  remain independently useful when neither is installed.
- Do not add direct CMS or social publishing.
- Do not write credential values to files. Provider configuration stores only
  environment-variable names.

## Licensing boundary

The public MIT content from `AgriciDaniel/claude-blog` may be adapted with its
copyright retained. Never copy anything from that repository's separately
licensed `brain/` subtree. Keep Apache, MIT, and CC BY 4.0 attribution headers
and notices intact.

## Engineering practice

Make the smallest change that satisfies the request. Preserve unrelated work,
including concurrent edits. Add or update a focused test for behavior changes.
Run `python3 scripts/validate_repo.py` and the relevant pytest targets before
hand-off.

Before any commit, confirm `git config user.email` equals
`253661133+BruceL017@users.noreply.github.com`. Never use a private mailbox for
author or committer identity.
