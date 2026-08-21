# Troubleshooting

## A Skill is not visible

Confirm installation with `codex plugin list`, reinstall
`codex-blog@brucel017-codex-blog`, and start a new Codex task. Skill discovery is
task-scoped; an already open task may retain the old plugin version.

## The CLI is not found

Full installation places the launcher in `${CODEX_HOME}/bin`. Add that directory
to `PATH`, or run the plugin package directly after `pip install -e`.
Marketplace-only installation intentionally does not create the launcher.

## Install refuses to replace an Agent

The same filename exists and is not provably managed by Codex Blog. Preserve or
rename the file, install interactively and review the prompt, or use `--yes`
only after confirming replacement is intended.

## An adapter cannot parse a file

Run the corresponding `codex-blog adapter` command to isolate the error. A
malformed optional brief or material package should be removed from the request
so Blog can continue independently. Do not convert an ambiguous value into a
fact merely to make parsing pass.

## Markdown exists but HTML or PDF does not

This is expected degradation when an optional renderer or platform library is
missing. Inspect `run-manifest.json` and install the `render` extra if the
artifact is required:

```bash
python -m pip install -e 'plugins/codex-blog[render]'
```

Rerun finalization. Do not regenerate the article.

## External link checks fail

Temporary network failures do not invalidate supported content. The stage tries
twice, then records a warning. Use `--skip-external-links` in a controlled
offline run, or rerun later. A known broken or misleading citation must still be
fixed before publication.

## No image was generated

That is the default. Image mode is deferred and no provider is called until the
user opts in. Use the Codex end-of-run choice or an explicit `codex-blog image`
resume command. Only after choosing API generation, verify the user-private
`${CODEX_HOME}/codex-blog/config.json` and its named environment variable, or
pass a trusted file with `image generate --config`. Project
`.codex-blog/config.json` files are ignored.

## A custom image endpoint fails

Check `kind`, `base_url`, `model`, `api_key_env`, and HTTPS reachability. Custom
hosts require a dedicated `CODEX_BLOG_IMAGE_*` credential name; official
`OPENAI_API_KEY` and `GEMINI_API_KEY` defaults cannot be sent to a custom host.
Never paste the key into configuration or an issue. A provider failure must
leave the article and prior artifacts unchanged.

## Uninstall preserves a file

The file changed after installation or was not owned by Codex Blog. This is
intentional. Review and remove it manually only when you are certain it is no
longer needed. Project outputs and Brain data are always user-owned.
