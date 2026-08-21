# Blog Write Delivery Checklist

Use this checklist after the article draft is saved. The authoritative state
model and retry policy are in
`skills/blog/references/blog-delivery-contract.md`.

## Core article (blocking)

- Markdown exists at `.codex-blog/output/<slug>/<slug>.md`.
- Frontmatter has accurate title, description, slug, and project-required keys.
- One H1, non-skipping H2/H3 hierarchy, complete body, and conclusion.
- Topic and search intent are answered without keyword stuffing.
- Material claims are supported; confirmed errors and unverifiable numbers were
  corrected, qualified, or removed.
- No TODO, image/chart marker, broken embed, drafting instruction, or empty
  section remains.
- No private or `do not publish` material was exposed.

Only failure of this list can block the run. Resume from the saved checkpoint up
to three total attempts.

## Optional enhancements (non-blocking)

Attempt requested schema, HTML, PDF, SEO/GEO review, fact/link check, and platform
formats after the Markdown. Each receives one retry. Record a second failure and
move on.

Do not run image-related checks or tools while `image_mode` is `deferred`.
Missing cover, OG image, inline images, charts, and screenshots are not
warnings in that mode.

## Completion summary

Report:

```text
Status: complete | complete_with_warnings
Article: <absolute-or-project-relative path>
Primary keyword: <value or "derived; demand unknown">
Optional artifacts: <paths or "none">
Degraded/skipped: <stage: reason, or "none">
```

Then, only for deferred mode, ask the single image question defined by the main
delivery contract. When images were explicitly requested, run them last and add
their paths/provider/model to the manifest without changing article prose.
