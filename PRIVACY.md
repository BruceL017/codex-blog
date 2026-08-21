# Privacy

Codex Blog has no telemetry, hosted control plane, or project account. Core
article planning, normalization, drafting state, manifests, and reports stay in
the user's workspace under `.codex-blog/` unless the user chooses another path.

## Network access

Network access occurs only when a requested workflow needs current research,
link checking, an optional external SEO integration, or explicitly approved
image generation. Default article creation does not probe image providers.
Installation does not configure or authenticate any image provider, MCP, or
external SEO Skill.

## Image-provider credentials

Provider secrets are read only from environment variables named in the
user-private `${CODEX_HOME}/codex-blog/config.json` or in an explicit trusted
file passed to `codex-blog image generate --config`. Project
`.codex-blog/config.json` files are deliberately ignored. Custom endpoints must
use a dedicated `CODEX_BLOG_IMAGE_*` environment variable; the default
`OPENAI_API_KEY` and `GEMINI_API_KEY` names are accepted only for their official
API hosts. The image configuration stores the environment-variable name, never
the image API secret itself. Image API secret values must not be written to
manifests, reports, logs, prompts, or generated articles. Codex Blog does not
manage Codex-native or MCP credentials.

## Optional Google data credentials

The separately invoked `blog-data` Google helpers use a different user-private
credential store. By default it is
`~/.config/codex-blog/google-api.json`, with
`CODEX_BLOG_GOOGLE_CONFIG` available as an explicit override. Unlike the image
provider configuration, this Google file may contain an `api_key` and
`ads_developer_token`, as well as paths and account/property identifiers. The
same values can instead come from their documented environment variables.

Google OAuth access and refresh tokens are stored by default in
`~/.config/codex-blog/oauth-token.json`, or at `CODEX_BLOG_GOOGLE_TOKEN`. The
helper writes its own configuration and token files atomically with user-only
file permissions. When their parent directory does not exist, it creates that
directory with user-only permissions; users who override the path to an
existing directory remain responsible for that directory's permissions. New
token saves strip the OAuth client secret and refer to the separately supplied
OAuth client file; legacy token files may still contain that field until
refreshed. Service-account and OAuth client JSON files remain at the
user-selected paths recorded in the private configuration.

These Google helpers run only when explicitly requested. Installation and the
default article pipeline do not create, read, or authenticate this credential
store.

## User content

Inputs and outputs may contain confidential drafts, analytics, customer data,
or unpublished plans. The user controls which files are supplied to an external
model or API and is responsible for provider retention policies. Codex Blog does
not publish to a CMS or social platform.

To remove local run data, delete the relevant project `.codex-blog/` directory.
The uninstaller intentionally preserves project output and user-owned Brain data.
