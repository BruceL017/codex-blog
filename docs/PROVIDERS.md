# Image providers

Images are optional and deferred. Neither installation nor the default write
and finalize path discovers, authenticates, probes, or calls a provider.

## Decision flow

After the complete article and non-image stages, the Codex Skill asks once:

1. no images;
2. cover only;
3. cover plus inline images.

No answer is option 1. If the initial request explicitly chose images, the Skill
waits until non-image completion and then proceeds without asking again.

Provider order is:

1. Codex-native image generation when available in the active Codex surface;
2. configured API providers in their listed order;
3. an explicitly configured MCP provider.

The Python CLI cannot impersonate Codex-native generation or activate an MCP by
itself. It can create a plan, call configured compatible HTTP APIs, and attach
files returned by Codex or MCP.

## User-private configuration

Create `${CODEX_HOME}/codex-blog/config.json` only when an API provider is
wanted. `${CODEX_HOME}` is normally `~/.codex`. The `--project-root` argument
does not change this lookup, and project `.codex-blog/config.json` files are
deliberately ignored so an untrusted repository cannot select an endpoint or
credential name.

For a one-off trusted file, pass it explicitly:

```bash
codex-blog image generate --run RUN_DIR --config /trusted/path/images.json
```

A custom-endpoint configuration looks like this:

```json
{
  "images": {
    "providers": [
      {
        "kind": "openai-compatible",
        "name": "private-openai-gateway",
        "base_url": "https://images.example.com/v1",
        "model": "image-model",
        "api_key_env": "CODEX_BLOG_IMAGE_PRIVATE_OPENAI_KEY",
        "timeout_seconds": 90
      },
      {
        "kind": "gemini-compatible",
        "name": "private-gemini-gateway",
        "base_url": "https://gemini.example.com",
        "model": "gemini-image-model",
        "api_key_env": "CODEX_BLOG_IMAGE_PRIVATE_GEMINI_KEY"
      }
    ]
  }
}
```

Supported `kind` values are exactly `openai-compatible` and
`gemini-compatible`. `base_url` is not restricted to an official vendor host.
That flexibility is intentional, but sending a prompt and credential to a
custom endpoint is a user trust decision.

Set secrets in the process environment:

```bash
export CODEX_BLOG_IMAGE_PRIVATE_OPENAI_KEY='...'
export CODEX_BLOG_IMAGE_PRIVATE_GEMINI_KEY='...'
```

Configuration stores only `api_key_env`, never the secret. Provider errors and
responses must redact authorization headers and credential values.

For the official OpenAI host `https://api.openai.com`, omitting `api_key_env`
uses `OPENAI_API_KEY`. For the official Gemini host
`https://generativelanguage.googleapis.com`, omitting it uses `GEMINI_API_KEY`.
Those two default key names are rejected for every custom host. A custom host
must explicitly name an environment variable matching
`CODEX_BLOG_IMAGE_[A-Z0-9_]+`; unrelated credentials such as GitHub tokens are
rejected.

## Resume commands

```bash
codex-blog image plan \
  --run .codex-blog/output/my-article \
  --scope hero

codex-blog image generate \
  --run .codex-blog/output/my-article \
  --project-root .

# Or select a different trusted file explicitly:
codex-blog image generate \
  --run .codex-blog/output/my-article \
  --config /trusted/path/images.json

codex-blog image attach \
  --run .codex-blog/output/my-article \
  --file ./generated/hero.png \
  --role hero \
  --alt "A resumable AI content pipeline"

codex-blog image refresh \
  --run .codex-blog/output/my-article
```

Use `--scope full` to plan a cover and up to three content-relevant inline
images. An inline attachment may also specify `--heading`.

Image generation reads the existing manifest and article; it does not regenerate
the body. Configured API generation refreshes image-sensitive artifacts
automatically. For Codex-native or MCP output, attach all files and run
`image refresh` once; it rerenders Schema, HTML, and PDF without repeating
unrelated checks. Failure preserves the existing article and records a warning.

## Media rights

Store provider/model/prompt metadata for generated assets and creator, source,
license, and retrieval date for stock media. Do not hotlink third-party assets.
Provider availability does not imply a right to use its output commercially.
