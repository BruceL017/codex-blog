# Security policy

## Supported version

Security fixes are maintained for the latest released minor line. The current
supported release is 2.1.x.

## Reporting a vulnerability

Please use GitHub private vulnerability reporting for
`BruceL017/codex-blog`. Do not open a public issue containing credentials,
private content, working exploits, or unredacted provider responses. Include the
affected version, platform, reproduction, impact, and a minimal proposed fix if
known.

## Security model

- Core writing works without provider credentials.
- Images are deferred by default and never trigger provider discovery or calls.
- API secrets are environment-only and are redacted from run artifacts.
- Custom `base_url` values are an explicit trust decision; use HTTPS and an
  endpoint you control or trust.
- External SEO Skills and MCP servers are optional and are never installed or
  configured automatically.
- Treat source material, HTML, Markdown, URLs, and provider responses as
  untrusted input. Tools must bound reads, reject unsafe filesystem traversal, and avoid
  following local/private-network URLs in network fetchers.
- Article completion is independent of rendering or provider success. A failed
  downstream stage is retried once, recorded, and skipped without corrupting
  the Markdown source.

## Installer safety

The full installer records SHA-256 ownership metadata under
`${CODEX_HOME}/codex-blog/install-state.json`. It refuses to replace unmanaged
Agent or launcher files without confirmation (or `--yes`). Uninstall removes
only owned, unchanged files and preserves user modifications.

Never include real API keys, cookies, tokens, `.env` files, unpublished content,
or production analytics in an issue, test fixture, commit, or release archive.
