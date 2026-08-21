# Architecture

Codex Blog separates reasoning surfaces from deterministic state and packaging:

```text
Codex user
  |
  +-- $blog / $blog-write / 31 specialist Skills
  |       |
  |       +-- 6 bounded TOML Agents
  |       +-- optional external Skill or MCP calls
  |
  +-- codex-blog CLI
          |
          +-- adapters -> SEOContentPacket -> BlogWriteRequest
          +-- run state and checkpoint management
          +-- deterministic validation/render/provider clients
          +-- .codex-blog/output/<slug>/
```

## Layers

The Marketplace manifest exposes Skills. Skills own intent routing, research,
writing, judgment, and the final image question. Agents are bounded roles for
research, writing, SEO, review, translation, and Brain curation; the calling
task owns the final article and does not treat an Agent response as automatic
publication approval.

The Python package owns input normalization, safe file handling, manifest
transitions, adapters, deterministic checks, rendering orchestration, and API
transport. It does not replace Codex as the article author. The CLI consumes
files and explicit arguments; only the Skill layer may activate another Skill.

## Article-first lifecycle

1. `prepare` resolves user input, explicit briefs, cluster context, materials,
   project context, and Blog research into `BlogWriteRequest`.
2. The Skill writes and checkpoints `<slug>.md`. If generation is interrupted,
   it resumes up to three times. Failure to produce a structurally complete
   article is the only core blocker.
3. A review pass fixes or removes confirmed errors. Unsupported numeric claims
   are qualified or removed and recorded in `review.md`.
4. `finalize` attempts Schema, HTML, PDF, SEO/GEO, facts/links, a handoff for
   the currently detected platform target, and the delivery report. Each stage
   has two total attempts. It then becomes `complete`, `degraded`, or `skipped`
   without rerunning successful work.
5. A deferred run stops with images `not_requested` and the Skill asks once.
   Later image commands resume from the manifest and update only affected
   artifacts.

The run status is `complete` when all attempted stages finish and
`complete_with_warnings` when optional work degrades. Image deferral alone is
not a warning.

## Data precedence and provenance

Precedence is current user instruction, explicit brief or cluster plan,
material package, project brand/persona, then Blog research. The normalizer
records material conflicts and source provenance. Lower-priority fields may fill
gaps but cannot silently replace higher-priority values.

Material fact states remain one of `verified`, `engineering`, `hypothesis`,
`failed`, or `unknown`. An adapter is not a verification service. Publication
boundaries and maturity labels survive normalization.

## Independence boundary

Codex SEO and `extract-seo-materials` are upstream compatibility contracts, not
runtime dependencies. Their source is neither imported nor vendored. Invalid or
missing adapter input becomes a declared data gap, and Blog's own research and
brief pipeline continues whenever the user supplied a sufficiently clear topic.

The same rule applies to rendering and image providers. Optional packages and
network services enrich the publication bundle but cannot revoke a valid
Markdown article.

## Brain

Brain data combines project-local context with user-owned persistent data under
Codex Blog's data directory. Records carry provenance and remain inspectable.
The design and implementation are clean-room and exclude the separately
licensed upstream `brain/` subtree.
