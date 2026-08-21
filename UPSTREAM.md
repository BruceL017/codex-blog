# Upstream lineage and clean-room boundary

Codex Blog 2.1.1 ports the public MIT distribution of
[AgriciDaniel/claude-blog 2.1.1](https://github.com/AgriciDaniel/claude-blog/tree/v2.1.1)
to OpenAI Codex. It is an independent community project and is not an official
release from OpenAI or AgriciDaniel.

The clean-room port was compared against upstream tag `v2.1.1`, commit
`aec971ac511370c6216cd93776c9cf2fec97b32a`. Runtime contracts were rewritten
for Codex; this repository is not a byte-for-byte redistribution.

## Ported public surface

The port retains the public project's editorial methods, templates, automation
scripts, attribution-bearing FLOW material, and the broad capability inventory.
Runtime-specific Claude commands, agents, plugin manifests, paths, and delivery
contracts are replaced with Codex Skills, TOML Agents, Marketplace metadata,
and an article-first runtime.

Notable command renames include:

| Upstream concept | Codex Blog |
|---|---|
| NotebookLM research | `blog-sources` |
| Google data workflow | `blog-data` |
| Audio generation | `blog-narration` narration and Gemini TTS generation |
| Content update | `blog-rewrite` / refresh workflow |

## Community design lineage

`blog-cluster` retains the cluster Plan/Execute and context-injection design
credited by upstream to Lutfiya Miller's `semantic-cluster-engine`. The
historical source is currently unavailable; `NOTICE` identifies a public copy
with a parentless commit attributed to Lutfiya Miller and preserves its MIT
notice. Codex Blog ports the
claude-blog 2.1.1 integration and changes its runtime and delivery contracts.

The multilingual Skills retain the design credit that upstream gives Chris
Mueller's `claude-blog-multilingual`. That original repository declares no
license, so no file from it is copied here. The material in Codex Blog comes
only from AgriciDaniel's security-reviewed, clean-room integration in the
MIT-licensed claude-blog 2.1.1 distribution.

The upstream image-prompt reference named the MIT-licensed Banana Claude project
and a March 2026 Google "Ultimate Prompting Guide." Banana Claude is verifiable,
but no official Google publication matching that title and date was identified.
Codex Blog therefore replaces the complete file with independently written,
provider-neutral guidance rather than redistributing mixed-provenance prose.

## Brain exclusion

The upstream repository contains a `brain/` subtree under a separate,
restrictive license. No file, prompt, template, documentation passage, test, or
implementation from that subtree may enter this repository.

Codex Blog's `blog-brain` capability is a clean-room implementation based on
the requested public behavior: project-local knowledge plus user-level data,
explicit provenance, and no hidden service dependency. Similar behavior or
terminology does not imply copied implementation.

## Compatibility, not dependency

Codex SEO and `extract-seo-materials` are optional adapters. Their source code is
not vendored, imported, modified, or required. Codex Blog consumes documented
files and normalized data contracts, and remains capable of researching,
planning, writing, reviewing, and packaging an article without either project.

See `NOTICE` and `THIRD_PARTY.md` for all retained attributions.
