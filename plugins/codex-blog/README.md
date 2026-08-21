# Codex Blog plugin

This directory is the distributable `codex-blog` Marketplace plugin. It contains
33 Skills, six TOML Agents, the standard-library core runtime, schemas, scripts,
and the `codex-blog` Python package.

Primary Codex entrypoints:

```text
$blog write <topic, keyword, brief, or materials>
$blog-write <topic, keyword, brief, or materials>
```

The complete Markdown article is the hard deliverable. Downstream stages retry
once and degrade without blocking it. Image mode defaults to `deferred`; image
providers are not probed or called until the user opts in after non-image work.

Install from the repository Marketplace:

```bash
codex plugin marketplace add BruceL017/codex-blog --ref v2.1.1
codex plugin add codex-blog@brucel017-codex-blog
```

For the six global Agents and CLI launcher, use the repository-level installer.
No provider, MCP, API secret, Codex SEO Skill, or external material Skill is
configured automatically.

Full documentation: <https://github.com/BruceL017/codex-blog>

MIT, with retained upstream and third-party notices. The restricted upstream
`brain/` subtree is not included.
