# Publication handoff

Codex Blog creates a publication package; it does not sign in to a CMS, publish
a post, schedule social content, or modify a production site.

Project detection recognizes nine classes: Next.js/MDX, Astro, Hugo, Jekyll,
WordPress, Ghost, Eleventy, Gatsby, and a static Markdown fallback. Detection
selects the current target and creates that target's handoff; it does not emit
all nine variants, deploy, or write into a live site.

Before publication, review:

- the complete Markdown article and all claims marked in `review.md`;
- title, slug, meta description, headings, links, and author attribution;
- generated Schema against the visible page content;
- HTML/PDF output when those optional stages completed;
- image rights, alt text, credits, and provider/model metadata;
- locale, internal-link targets, and any platform-specific variant;
- `run-manifest.json` warnings and skipped stages.

`complete_with_warnings` means the article is deliverable but at least one
optional check or artifact did not complete. It is not permission to ignore a
known factual contradiction. Confirmed errors must be fixed or removed before
publication.
