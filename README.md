# Codex Blog

Article-first SEO content production for OpenAI Codex.

[中文说明](docs/README.zh-CN.md) · [Installation](docs/INSTALLATION.md) ·
[Architecture](docs/ARCHITECTURE.md) · [Providers](docs/PROVIDERS.md) ·
[Skills](docs/SKILLS.md)

Codex Blog ships as a Codex Marketplace repository with **33 Skills**, **6 TOML
Agents**, a deterministic Python CLI, ownership-aware installers, optional SEO
adapters, and a complete publication-package workflow.

The product has one hard promise: **finish and save the complete SEO Markdown
article first**. Schema, HTML, PDF, quality checks, link checks, and platform
handoff are downstream enhancements. Each failed downstream stage is retried
once, then skipped with an explanation instead of withholding the article.

Images are different by design: they are **off during the default run**. After
all non-image work, the Codex Skill asks once whether to generate no images, a
cover only, or a cover plus inline images. No answer means no image calls.

This is an independent community project. It is not affiliated with or endorsed
by OpenAI, AgriciDaniel, Codex SEO, or any provider named in the documentation.

## What it does

- Turns a topic, primary keyword, SEO brief, source files, or content-material
  package into a complete, publication-ready article.
- Researches and builds its own brief when no external SEO Skill is available.
- Preserves fact state, source provenance, publication boundaries, brand voice,
  search intent, internal links, and content-cluster context.
- Produces metadata, structured headings, supported citations, internal-link
  suggestions, conclusion, and intent-appropriate FAQ content.
- Attempts Schema, HTML, PDF, SEO/GEO review, fact/link review, a current-target
  platform handoff, and a delivery report without allowing those stages to
  block Markdown.
- Resumes image work from `run-manifest.json` without rewriting the article.
- Supports project-local and user-level clean-room Brain knowledge.
- Plans strategy, calendars, briefs, outlines, rewrites, clusters, translations,
  localization, repurposing, taxonomy, content decay, and FLOW workflows.
- Produces narration scripts and, only when explicitly authorized, can use the
  bundled Gemini TTS compatibility generator for audio files.
- Detects nine project classes—Next.js/MDX, Astro, Hugo, Jekyll, WordPress,
  Ghost, Eleventy, Gatsby, or static Markdown—and creates a handoff for the
  currently detected target without publishing.

## Install

Requirements: Codex CLI with plugin support and Python 3.10 or newer.

Marketplace-only installation exposes the 33 Skills:

```bash
codex plugin marketplace add BruceL017/codex-blog --ref v2.1.1
codex plugin add codex-blog@brucel017-codex-blog
```

The full installer also copies the six TOML Agents to `${CODEX_HOME}/agents`
and creates the `codex-blog` launcher in `${CODEX_HOME}/bin`:

```bash
git clone --branch v2.1.1 https://github.com/BruceL017/codex-blog.git
cd codex-blog
./install.sh
```

Windows PowerShell:

```powershell
git clone --branch v2.1.1 https://github.com/BruceL017/codex-blog.git
Set-Location codex-blog
.\install.ps1
```

The installer never configures an image provider, MCP server, API key, Codex
SEO, or `extract-seo-materials`. See [Installation](docs/INSTALLATION.md) for the
ownership and uninstall behavior.

## Use in Codex

Start with a keyword and let Codex Blog do the rest:

```text
$blog write
Primary keyword: AI content pipeline
Audience: content teams
Language: English
Write a complete SEO article. Do not generate images unless I approve them at the end.
```

Use the direct writer for compatibility with Codex SEO:

```text
$blog-write
Use ./seo-brief.json and ./_content_materials/sessions/project-seo-materials.md.
Primary keyword: AI content pipeline
Create the complete article and preserve source/fact-state metadata.
```

Natural-language invocation works too: “Use Codex Blog to turn this keyword and
these materials into a complete Chinese SEO article.” Output follows the user's
language; Skill and CLI names remain English.

## Independent core and optional adapters

Codex Blog always has its own research, brief, outline, drafting, editing, and
packaging workflow. Integrations only enrich its normalized input.

```text
Codex SEO brief / cluster-plan.json ─┐
extract-seo-materials v1/v2 ────────┼─> SEOContentPacket
inline user input / ordinary files ─┘          │
                                               v
                                      BlogWriteRequest
                                               │
                              complete SEO Markdown first
                                               │
                              non-blocking downstream stages
                                               │
                                  one final image decision
```

Input precedence is fixed: current user instruction, explicit brief or cluster
plan, material package, project brand/persona, then Codex Blog's own research.
Conflicts are recorded instead of silently overwriting higher-priority input.
Hypotheses from `extract-seo-materials` never become verified facts merely
because they entered the writing pipeline.

If an adapter is absent or its file is malformed, Codex Blog records the gap and
continues independently when the topic and intent remain clear.

## Deferred images

Default `image_mode` is `deferred`. The default run:

- does not call Codex-native image generation;
- does not inspect API or MCP provider availability;
- creates no visual placeholder, cover, OG asset, SVG chart, or screenshot;
- does not lower article quality because an image is missing.

At the end, choose no images, cover only, or cover plus inline images. An
explicit image request in the initial prompt skips the question but still waits
until the article and non-image work are complete.

Provider order is Codex-native generation, configured API providers, then MCP.
Configured APIs may be OpenAI-compatible or Gemini-compatible and may use a
custom `base_url`. The CLI reads provider settings from the user-private
`${CODEX_HOME}/codex-blog/config.json` by default or from the file passed to
`image generate --config`; project `.codex-blog/config.json` files are ignored.
Secrets are read only from environment variables. See [Providers](docs/PROVIDERS.md).

## Output

Each run uses `.codex-blog/output/<slug>/` by default:

```text
<slug>.md              required complete article
request.json           normalized input
run-manifest.json      stage status, attempts, warnings, artifacts
review.md              editorial and verification notes
schema.json            optional structured data
<slug>.html            optional render
<slug>.pdf             optional render
platform/              optional current-target handoff
images/                created only after explicit opt-in
```

The final run state is `complete` or `complete_with_warnings`. A genuinely
incomplete core article is `blocked`; a missing renderer or provider is not.

## CLI and verification

The CLI supports deterministic setup, normalization, validation, rendering,
manifest inspection, and resumable image operations. Discover the installed
surface with:

```bash
codex-blog --help
codex-blog doctor
codex-blog image plan --run .codex-blog/output/my-article --scope hero
```

Repository verification:

```bash
python3 scripts/validate_repo.py
python3 -m pytest -q tests plugins/codex-blog/tests
```

## Origin and license

The public capability set is ported from
[AgriciDaniel/claude-blog 2.1.1](https://github.com/AgriciDaniel/claude-blog/tree/v2.1.1)
under MIT. Its separately licensed `brain/` subtree is excluded; Codex Blog's
Brain implementation is clean-room. FLOW prompt material remains CC BY 4.0 and
retains per-file attribution.

See [LICENSE](LICENSE), [NOTICE](NOTICE), [THIRD_PARTY.md](THIRD_PARTY.md), and
[UPSTREAM.md](UPSTREAM.md). Complete third-party license texts are in
[`LICENSES/`](LICENSES/).
