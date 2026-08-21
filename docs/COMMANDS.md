# Command reference

Codex Skills are the primary content interface. The Python CLI owns repeatable
file contracts, manifests, adapters, checks, and resumable image operations.

## Core Skills

```text
$blog write <request>
$blog-write <request>
```

`$blog` routes the complete workflow. `$blog-write` is the direct writer and
the stable compatibility target for Codex SEO. Both accept topic, keywords,
brief/material paths, language, template, target length, site context, cluster
context, and an explicit image request.

Specialist invocation follows the directory name, for example `$blog-brief`,
`$blog-outline`, `$blog-rewrite`, `$blog-seo-check`, `$blog-schema`,
`$blog-localize`, and `$blog-flow`. See [Skills](SKILLS.md).

## CLI setup and run preparation

```bash
codex-blog init [--project-root PATH]

codex-blog prepare [TOPIC] \
  [--keyword KEYWORD] \
  [--secondary-keyword KEYWORD ...] \
  [--intent INTENT] [--audience AUDIENCE] \
  [--brief FILE] [--materials FILE ...] \
  [--cluster-plan FILE] [--cluster-post ID] \
  [--site-root PATH] [--language LOCALE] \
  [--template NAME] [--word-count NUMBER] \
  [--images[=hero|full]] [--output-root PATH]
```

`write` is an alias for `prepare`. Without `--images`, image mode is deferred.
`--images` alone means `full`; use `--images=hero` for a cover only.

`prepare` normalizes input and creates run state. The Codex Skill writes the
article body into the requested run directory.

## Finalization and inspection

```bash
codex-blog finalize --run RUN_DIR \
  [--article FILE] [--project-root PATH] [--skip-external-links]

codex-blog preflight --run RUN_DIR
codex-blog show --run RUN_DIR
codex-blog doctor [--project-root PATH]
```

Finalization applies the one-retry policy to non-image downstream stages. The
default finalize path never calls or probes an image provider.

## Adapters

```bash
codex-blog adapter brief FILE
codex-blog adapter cluster FILE [--post ID]
codex-blog adapter materials FILE
```

Adapters parse files only. They do not install or invoke Codex SEO or
`extract-seo-materials`.

## Brain

```bash
codex-blog brain add --scope project|user [--project-root PATH] \
  --title TITLE [--content TEXT | --file FILE] [--tag TAG ...]
codex-blog brain list --scope project|user [--project-root PATH] [--tag TAG]
codex-blog brain context [--project-root PATH] [--max-chars NUMBER]
```

Brain is a clean-room local knowledge layer, not the excluded upstream
implementation. Project scope is the default; user scope requires an explicit
choice and remains user-owned during uninstall.

## Images

```bash
codex-blog image plan --run RUN_DIR --scope hero|full
codex-blog image generate --run RUN_DIR [--project-root PATH] [--config FILE]
codex-blog image attach --run RUN_DIR --file FILE --role hero|inline \
  [--heading HEADING] [--alt TEXT]
codex-blog image refresh --run RUN_DIR
```

These are explicit resume operations. They never rewrite the article body.
`generate` refreshes image-sensitive artifacts automatically. After one or more
Codex-native or MCP files are attached, run `image refresh` once to rerender
Schema, HTML, and PDF without repeating unrelated stages.

`generate` reads `${CODEX_HOME}/codex-blog/config.json` by default. `--config`
selects an explicit trusted file. It never discovers a project
`.codex-blog/config.json`, even when `--project-root` is supplied.

## Bundled deterministic tools

```bash
codex-blog run <bundled-script.py> [arguments...]
```

Only shipped scripts are accepted. This is not an arbitrary Python execution
interface.
