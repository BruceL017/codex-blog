# Installation

## Requirements

- OpenAI Codex CLI with plugin support
- Git
- Python 3.10 or newer

Core runtime uses the standard library. Optional analysis and rendering extras
are not installed by the repository installer.

## Marketplace installation

```bash
codex plugin marketplace add BruceL017/codex-blog --ref v2.1.2
codex plugin add codex-blog@brucel017-codex-blog
```

This makes all 33 Skills available. It does not copy the six TOML Agents to the
global Agent directory or add a CLI launcher.

## Full installation

macOS and Linux:

```bash
git clone --branch v2.1.2 https://github.com/BruceL017/codex-blog.git
cd codex-blog
./install.sh
```

Windows PowerShell:

```powershell
git clone --branch v2.1.2 https://github.com/BruceL017/codex-blog.git
Set-Location codex-blog
.\install.ps1
```

Use `--yes` only when you intentionally want a noninteractive install to replace
a conflicting, unmanaged Agent or launcher. Add `${CODEX_HOME}/bin` (normally
`~/.codex/bin`) to `PATH` after installation.

The installer:

1. validates Python and the Codex CLI;
2. adds this repository as Marketplace `brucel017-codex-blog`;
3. installs `codex-blog@brucel017-codex-blog`;
4. discovers the actual plugin source with `codex plugin list --json`;
5. copies exactly six TOML Agents to `${CODEX_HOME}/agents`;
6. creates `${CODEX_HOME}/bin/codex-blog` (or `.cmd` on Windows);
7. writes ownership and SHA-256 state to
   `${CODEX_HOME}/codex-blog/install-state.json`.

It does not install optional Python extras, configure providers, create the
user-private `${CODEX_HOME}/codex-blog/config.json`, register MCPs, set
environment variables, or install Codex SEO / `extract-seo-materials`. Runtime
provider lookup also ignores project `.codex-blog/config.json` files.

## Idempotency and ownership

Running the installer again updates files that it still owns. A same-name file
with user changes is preserved unless the user confirms replacement. A matching
file that existed before the first install is recorded as unowned.

The installer refuses to silently repoint an existing Marketplace with the same
name to a different repository. It also avoids guessing Codex cache paths.

## Optional Python extras

For local development or direct package installation:

```bash
python -m pip install -e plugins/codex-blog
python -m pip install -e 'plugins/codex-blog[analysis]'
python -m pip install -e 'plugins/codex-blog[render]'
```

Release wheels are standalone CLI distributions: the build embeds Skills,
Agents and their generation sources, schemas, deterministic helper scripts,
data, plugin metadata, and license/lineage notices under the package's private
`_bundle` resource directory, including the complete Apache 2.0 and CC BY 4.0
legal texts. It does not duplicate runtime resources in the maintained source
tree. Installing a wheel exposes the full CLI but does not register the
Marketplace or copy global TOML Agents; use the repository installer for Codex
integration.

WeasyPrint may require platform libraries. A missing optional dependency causes
the relevant downstream stage to degrade; it never invalidates Markdown.

## Upgrade

Check out the new release and rerun the full installer. It reuses ownership state
and updates only managed files. Start a new Codex task after reinstalling so the
new Skill definitions are loaded.

## Uninstall

```bash
./uninstall.sh
```

Windows:

```powershell
.\uninstall.ps1
```

Uninstall refuses to run without scoped install state. It removes only owned,
unchanged Agents and launchers, then removes the plugin/Marketplace only when
the installer originally added them. Modified files, project `.codex-blog/`
outputs, provider configuration, and user Brain data are preserved.
