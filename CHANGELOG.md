# Changelog

All notable changes are documented here. Versions follow Semantic Versioning.

## [2.1.2] - 2026-08-21

### Changed

- Expanded `$blog` and `$blog-write` discovery metadata for English and Chinese
  SEO content creation, SEO article writing, and keyword-driven article requests.
- Aligned Marketplace keywords and Skill UI prompts with the writing workflow.

## [2.1.1] - 2026-08-21

### Added

- Initial Codex Marketplace distribution with 33 Skills and 6 TOML Agents.
- Article-first `$blog` and `$blog-write` workflows with checkpoint recovery.
- Stable `BlogWriteRequest` and `SEOContentPacket` adapter contracts.
- Optional Codex SEO and `extract-seo-materials` file adapters.
- Deterministic CLI, run manifest, downstream degradation, and resumable images.
- OpenAI-compatible, Gemini-compatible, Codex-native, and MCP image paths.
- Ownership-aware Unix and Windows installation and uninstallation.

### Changed

- Complete SEO Markdown is the only hard delivery artifact.
- Image generation is deferred until the final opt-in question.
- Each non-core downstream stage receives one retry, then is skipped with a
  recorded warning.
- Claude-specific runtime surfaces were replaced with Codex Skills, Agents,
  Marketplace metadata, and project configuration.

### Licensing

- Preserved the upstream MIT notice and all Apache/MIT/CC BY attribution.
- Reimplemented Brain behavior clean-room; the restricted upstream `brain/`
  subtree is excluded.
