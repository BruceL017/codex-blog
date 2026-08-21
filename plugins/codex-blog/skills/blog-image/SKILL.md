---
name: blog-image
description: >
  Generate or edit blog cover and inline images only after the user explicitly
  requests visuals. Use for `$blog image` or the final image stage of a completed
  Blog run; supports Codex-native image generation, configured OpenAI-compatible
  or Gemini-compatible APIs with custom base URLs, and configured MCP providers.
license: MIT
metadata:
  author: AgriciDaniel
  codex-port: BruceL017
  version: "2.1.1"
---

# Blog Image

Run only after explicit visual intent. Invocation of `$blog image` is explicit
intent; a normal `$blog write` is not. When called from the writing pipeline,
verify that `run-manifest.json` records `hero` or `full`, or that the
user just approved the final image question.

Writing defaults to `image_mode=deferred`. While deferred, do not invoke this
Skill, probe providers, or create visual artifacts. The article and requested
non-image stages must finish before image work starts.

## Ordering invariant

The complete article and requested non-image stages must exist before image
generation. Read the article/manifest to derive concepts, but do not rewrite
article prose. If no article exists for an orchestrated run, return a diagnostic
instead of generating unrelated assets.

## Commands

| Invocation | Behavior |
|---|---|
| `$blog image cover <article-or-manifest>` | One cover/Hero image |
| `$blog image inline <article-or-manifest>` | Up to three useful inline images |
| `$blog image all <article-or-manifest>` | Cover plus inline images |
| `$blog image edit <image> <instruction>` | Edit an existing image |
| `$blog image doctor` | Read-only report of configured providers |

A bare approval from `$blog write` maps to `full`: one cover and up to three
inline images. `$blog image cover` persists `hero`; `$blog image all` persists
`full`. Reuse the cover for Open Graph unless a separate social card was
requested. Do not generate decorative images that add no meaning.

## Provider order

Try only configured/available providers, in this order:

1. Codex-native image generation (`$imagegen` or the current native image tool).
2. Configured HTTP provider:
   - OpenAI-compatible images endpoint, including a user-configured `base_url`;
   - Gemini-compatible generate-content/image endpoint, including a custom
     `base_url`.
3. Configured image-capable MCP server.

Provider configuration may mix types. Use the explicit provider/model override
when supplied; otherwise follow the order above. Do not assume that an
OpenAI-compatible endpoint is hosted by OpenAI or that a Gemini-compatible
endpoint is hosted by Google.

For each configured provider, make one initial attempt and at most one retry
using the first failure diagnostic: two attempts per provider maximum. If both
attempts fail, continue to the next configured provider in the order above.
Never rerun a provider that already returned a validated asset.

API keys are referenced by environment-variable name in configuration and read
only at call time. Never put a key in the prompt, command line, manifest, logs,
or output metadata. Redact provider errors before reporting them. Do not install
an MCP server, modify Codex global configuration, or open a paid endpoint without
the authorization required by the current environment.

## Generate

1. Read the article, audience, locale, brand context, and existing images.
2. Select concepts that communicate the article's distinctive ideas. Use
   editorial, product, landscape, UI/web, infographic, or abstract direction as
   appropriate.
3. Write provider-neutral prompts specifying subject, composition, intended
   placement, aspect ratio, accessible contrast, brand constraints, and text
   policy. Avoid trademarks, private people, deceptive screenshots, and
   unsupported data graphics.
4. Generate the cover at a wide social-compatible ratio and inline assets at
   the ratio their section needs. Do not render statistics into an image unless
   they are verified and supplied.
5. Validate that returned files are actual images, non-empty, within the article
   output directory, and visually relevant. Record provider/model and prompt
   hash, never secrets.
6. Add descriptive alt text based on the actual image. Update the Markdown,
   schema, and rendered outputs only after the image file validates.

If no provider succeeds after those per-provider attempts, leave all
pre-existing artifacts untouched and mark the image stage
`skipped`/`complete_with_warnings`. Never add a placeholder or broken path.

## Edit

Resolve one explicit source image and preserve the original. Write edits to a
new file unless the user explicitly asks to replace it. Validate the result
before updating references. Describe material edits in the manifest.

## Output

Store assets under `.codex-blog/output/<slug>/images/` and update the existing
manifest with selected mode, provider type, model, prompt hash, dimensions,
files, alt text, and affected downstream stages. Do not change final status to
blocked for an image failure.

Read `references/prompt-engineering-blog.md` for domain-specific prompt details.
Provider-specific legacy references are optional compatibility notes, not core
requirements.
