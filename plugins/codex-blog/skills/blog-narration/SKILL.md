---
name: blog-narration
description: >
  Adapt a completed blog post into a narration, read-aloud, or two-speaker
  podcast script with pronunciation and production notes. Use for `$blog
  narration`; it produces a script by default and does not require a TTS vendor
  or generate audio unless the user separately authorizes a configured service.
license: MIT
metadata:
  author: AgriciDaniel
  codex-port: BruceL017
  version: "2.1.2"
---

# Blog Narration

Transform a finished article into spoken-language copy. The default artifact is
Markdown, not audio. This keeps narration useful without Google/Gemini SDKs,
credentials, or a particular API endpoint.

## Modes

| Invocation | Output |
|---|---|
| `$blog narration summary <file>` | 2-5 minute spoken summary |
| `$blog narration full <file>` | Complete read-aloud adaptation |
| `$blog narration dialogue <file>` | Host/guest podcast script |
| `$blog narration pronunciations <file>` | Pronunciation and acronym guide |

Write beside the article or under its output folder as
`narration-<mode>.md`. Preserve the article's facts, caveats, brand voice, and
source attributions, but rewrite visual references so they make sense in audio.
Do not read URLs, Markdown syntax, frontmatter, image alt text, code fences, or
schema aloud unless the user requests it.

## Script structure

- title, mode, estimated duration, language/locale, and source article path;
- cold open and clear promise;
- spoken sections with natural transitions;
- speaker labels for dialogue mode;
- pronunciation notes for names, acronyms, numbers, and technical terms;
- optional pauses, emphasis, music/SFX cues, and chapter timestamps;
- concise closing and call to action consistent with the article.

Never add claims, quotes, experience, or statistics absent from the article and
its approved source packet. When a citation is important, name the source in
natural speech and place the full URL in production notes.

## Optional audio handoff

If the user explicitly requests synthesized audio, provide the completed script
as the stable input to an already configured TTS API/MCP. Ask for authorization
before a paid or externally mutating call. Provider choice, voice, cost, and
audio-file generation are outside the default narration stage. A provider
failure leaves the narration script complete and is reported as a warning.

The bundled legacy Gemini TTS helpers are compatibility utilities only; do not
run or install them by default.
