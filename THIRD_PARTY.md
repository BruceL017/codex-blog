# Third-party notices

Codex Blog's original code and the ported public claude-blog surface are
MIT-licensed. The named FLOW prompt files retain their CC BY 4.0 license, and
the project preserves attribution for every public work it adapts.

## claude-blog 2.1.1

- Author: Daniel Agrici (`AgriciDaniel`)
- Source: <https://github.com/AgriciDaniel/claude-blog/tree/v2.1.1>
- License: MIT
- Use: public Skills, templates, scripts, tests, and editorial methodology were
  ported to Codex conventions.

The upstream MIT copyright is present in `LICENSE` and `NOTICE`. The upstream
`brain/` directory is not MIT-licensed and is not included or copied.

## semantic-cluster-engine

- Contributor: Lutfiya Miller
- Historical source: <https://github.com/Drfiya/semantic-cluster-engine>
- Verifiable archive: <https://github.com/thenguyenvn90/semantic-cluster-engine/tree/86ceb6ecf60b0b4f16d67dfa52b30a69ad57f14d>
- License: MIT in the archived root commit
- License URI:
  <https://github.com/thenguyenvn90/semantic-cluster-engine/blob/86ceb6ecf60b0b4f16d67dfa52b30a69ad57f14d/LICENSE>
- Legal text: [`LICENSES/semantic-cluster-engine-MIT.txt`](LICENSES/semantic-cluster-engine-MIT.txt)
- Integration provenance:
  <https://github.com/AgriciDaniel/claude-blog/blob/aec971ac511370c6216cd93776c9cf2fec97b32a/docs/CONTRIBUTORS.md#v170-pro-hub-challenge-community-release-2026-04-27>
- Use: Plan/Execute cluster architecture, shared cluster context, and
  pillar-and-spoke execution retained through claude-blog's `blog-cluster`.

The historical URI returned 404 during the 2026-08-21 audit. The archive's
parentless commit `86ceb6ecf60b0b4f16d67dfa52b30a69ad57f14d` records Lutfiya
Miller as author and committer and contains the retained MIT notice. Codex Blog
does not copy from the archive directly: it ports the version published in
MIT-licensed claude-blog 2.1.1. Changes include Codex command routing, deferred
images, article-first batch delivery, manifest recovery, and provider-neutral
integrations.

## claude-blog-multilingual

- Contributor: Chris Mueller (`Chriss54`)
- Current source: <https://github.com/Chriss54/claude-blog-multilingual>
- Historical URI: <https://github.com/Chriss54/multilingual-int>
- Original repository license: none declared as of 2026-08-21
- Integration provenance:
  <https://github.com/AgriciDaniel/claude-blog/blob/aec971ac511370c6216cd93776c9cf2fec97b32a/docs/CONTRIBUTORS.md#v170-pro-hub-challenge-community-release-2026-04-27>
- Use: design lineage for multilingual orchestration, translation,
  localization, and locale auditing.

The original repository is credited for the design but its files are not
redistributed. Codex Blog ports only AgriciDaniel's security-reviewed,
clean-room integration published within the MIT-licensed claude-blog 2.1.1
distribution. Changes include Codex routing and paths, image deferral,
standalone fallbacks, and optional Codex SEO interoperability.

## impeccable 3.1.1

- Author: Paul Bakaus
- Source: <https://github.com/pbakaus/impeccable>
- License: Apache License 2.0
- Legal text: [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt)
- Use: editorial adaptations of AI-pattern detection, ordinal heuristics,
  cognitive-load review, and durable context loading.

No impeccable code is represented as original Codex Blog work. Per-file
attribution in the adapted references and `NOTICE` must be retained.

## last30days-skill 3.2.1

- Author: Matt Van Horn
- Source: <https://github.com/mvanhorn/last30days-skill>
- License: MIT
- Use: research-quality scoring, synthesis rules, keyword-trap classification,
  entity decomposition, and API-free discourse research methodology.

The upstream service/API implementation is not redistributed.

## FLOW 1.0.0

- Author: Daniel Agrici
- Source: <https://github.com/AgriciDaniel/flow>
- License: CC BY 4.0 for prompt content; MIT for Skill code
- License URI: <https://creativecommons.org/licenses/by/4.0/>
- Legal text: [`LICENSES/CC-BY-4.0.txt`](LICENSES/CC-BY-4.0.txt)
- Use: Find, Leverage, Optimize, and Win framework material under
  `plugins/codex-blog/skills/blog-flow/references/`.

Codex Blog changed the FLOW material by selecting blog-applicable prompts,
adding sync/attribution headers and index metadata, and adapting its application
guidance. All FLOW prompt files must retain their CC BY 4.0 header. Modified or
republished prompt content must continue to identify Daniel Agrici, link to the
source and license, and state that changes were made.

## Banana Claude and Google image guidance (not redistributed)

- Banana Claude source: <https://github.com/AgriciDaniel/banana-claude/tree/a4b5a7e4f592029886a379496cf29980fb6b8824>
- Banana Claude license: MIT, Copyright (c) 2026 AgriciDaniel
- Banana Claude license URI:
  <https://github.com/AgriciDaniel/banana-claude/blob/a4b5a7e4f592029886a379496cf29980fb6b8824/LICENSE>
- Google Gemini image documentation:
  <https://ai.google.dev/gemini-api/docs/image-generation>
- Google Imagen prompt guide:
  <https://ai.google.dev/gemini-api/docs/imagen-prompt-guide>

The claude-blog reference previously named Banana Claude and a March 2026
Google "Ultimate Prompting Guide." Banana Claude's license is verifiable, but
no official Google publication matching that title and date was identified in
the audit. To avoid redistributing mixed-provenance prose, Codex Blog replaced
the complete reference with independently written guidance. The links above
are retained only for factual provider verification; no Banana Claude or
Google prompt-guide content is bundled from those sources.

## Services and APIs

OpenAI-compatible endpoints, Gemini-compatible endpoints, MCP servers,
Openverse, Unsplash, Pexels, Pixabay, and other named providers are optional
external services. Their software and media are not included. Users are
responsible for provider terms, model policies, and asset licenses.
