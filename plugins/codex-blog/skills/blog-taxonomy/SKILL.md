---
name: blog-taxonomy
description: >
  Extract, suggest, and prepare tags and categories for blog posts across major
  CMS platforms. Produces WordPress, Shopify, Ghost, Strapi, and Sanity handoff
  payloads without contacting a CMS. Generates tag suggestions from content
  analysis (keyword frequency, heading extraction, semantic grouping), enforces
  minimum post-count thresholds to prevent thin tag archives, and writes taxonomy
  handoff files. Use when user says "tags", "categories", "taxonomy",
  "tag suggestions", "sync tags", "WordPress tags", "Shopify tags".
license: MIT
---

# Blog Taxonomy

Manage tags, categories, and topic clusters across CMS platforms.

## Commands

| Command | Purpose |
|---------|---------|
| `$blog taxonomy suggest <file>` | Extract candidate tags and categories from content |
| `$blog taxonomy sync <cms>` | Generate a CMS-ready taxonomy handoff without publishing |
| `$blog taxonomy audit [directory]` | Check for thin tags, orphan tags, taxonomy bloat |

## Tag Suggestion Workflow

### Step 1: Parse Content Structure

Read the target file and extract:
- All H2 and H3 headings (primary topic signals)
- Bold and italic phrases (emphasis signals)
- Existing frontmatter tags/categories if present

### Step 2: Frequency Analysis

Scan the body text for high-frequency phrases:
- 1-word terms: minimum 4 occurrences (excluding stop words)
- 2-word phrases: minimum 3 occurrences
- 3-word phrases: minimum 2 occurrences

Exclude common non-tag words: articles, prepositions, conjunctions, pronouns.

### Step 3: Semantic Grouping

Group related candidates into clusters:
- Merge singular/plural variants (keep the more common form)
- Merge hyphenated and non-hyphenated forms
- Group synonyms under the highest-frequency term

### Step 4: Deduplicate and Rank

- Fuzzy match on slugified names (Levenshtein distance <= 2)
- Do not auto-merge short slugs under 5 characters using Levenshtein alone; require token overlap or manual review
- Score each candidate: `(frequency * 2) + (heading_presence * 5) + (emphasis * 1)`
- Return top 5-10 ranked suggestions

### Output Format

```
## Tag Suggestions: [Post Title]

| Rank | Tag | Score | Source |
|------|-----|-------|--------|
| 1 | content-marketing | 18 | H2 + 6 mentions |
| 2 | seo-strategy | 14 | H3 + 4 mentions |
| 3 | keyword-research | 11 | 5 mentions + bold |

### Suggested Categories
- Primary: [best-fit category]
- Secondary: [optional second category]
```

## CMS Handoff Adapters

`sync` is a compatibility name for export. It writes a reviewable payload and
never sends a CMS request, reads CMS credentials, creates taxonomy entities, or
assigns tags to a live post. A human or a separate publishing system may apply
the handoff after review; that action is outside Codex Blog.

### Adapter Overview

| CMS | Handoff format | Tags model |
|-----|----------------|------------|
| WordPress | JSON entity and assignment payload | First-class entities with IDs |
| Shopify | GraphQL variables document | String array on Article |
| Ghost | JSON import fragment | First-class entities |
| Strapi | JSON entity fragment | User-defined content type |
| Sanity | JSON mutation document | Document type |

### WordPress Adapter

**Tag lookup descriptor**:
```
GET {CMS_URL}/wp-json/wp/v2/tags?per_page=100&search={keyword}
```

**Proposed tag entity payload**:
```
POST {CMS_URL}/wp-json/wp/v2/tags
Body: {"name": "Tag Name", "slug": "tag-name", "description": "Optional"}
```

**Category lookup descriptor** (hierarchical, supports parent field):
```
GET {CMS_URL}/wp-json/wp/v2/categories?per_page=100
```

**Proposed category entity payload**:
```
POST {CMS_URL}/wp-json/wp/v2/categories
Body: {"name": "Category", "slug": "category", "parent": 0}
```

**Proposed post assignment payload**:
```
POST {CMS_URL}/wp-json/wp/v2/posts/{id}
Body: {"tags": [1, 2, 3], "categories": [4]}
```

Pagination: follow `X-WP-TotalPages` header for full listing.

### Shopify Adapter

Tags on Shopify are string arrays on the Article object, not first-class entities.

**Article-tag GraphQL handoff**:
```graphql
mutation {
  articleUpdate(id: "gid://shopify/Article/123", article: {
    tags: ["tag-one", "tag-two", "tag-three"]
  }) {
    article { id tags }
    userErrors { field message }
  }
}
```

**List all tags in use** (GraphQL):
```graphql
{
  articles(first: 250, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    edges {
      node { id title tags }
    }
  }
}
```

The handoff records cursor requirements, but Codex Blog does not execute the
query or mutation.

Note: REST API marked legacy Oct 2024. GraphQL required for new apps since Apr 2025.

### Ghost Adapter

**Tag lookup descriptor**:
```
GET {CMS_URL}/ghost/api/admin/tags/?limit=all
```

**Proposed tag import fragment**:
```
POST {CMS_URL}/ghost/api/admin/tags/
Body: {"tags": [{"name": "Tag Name", "slug": "tag-name"}]}
```

Credential and JWT generation are intentionally outside this Skill.

### Strapi Adapter

Endpoint auto-generated from content types. Typical setup:

```
GET {CMS_URL}/api/tags?pagination[pageSize]=100
POST {CMS_URL}/api/tags
Body: {"data": {"name": "Tag Name", "slug": "tag-name"}}
```

Pagination: increment `pagination[page]` until all pages are exhausted.

Strapi v4 responses use the `data` wrapper with `attributes`; Strapi v5 uses
a flatter response shape. Detect the version or normalize both shapes before
deduplication. Check your content type schema for field names.

### Sanity Adapter

**Tag query descriptor** (GROQ):
```
*[_type == "tag"] { _id, name, slug }
```

**Proposed mutation document**:
```
POST https://{project_id}.api.sanity.io/{SANITY_API_VERSION}/data/mutate/{dataset}
Body: {"mutations": [{"create": {"_type": "tag", "name": "Tag", "slug": {"current": "tag"}}}]}
```

Default `SANITY_API_VERSION` to a current tested API date supplied by the
project environment; do not hard-code it in generated requests.

## Taxonomy Audit Workflow

### Step 1: Inventory

Scan all posts in the supplied local export or target directory. Build a map:
- tag_name -> [list of post files/IDs using this tag]
- category_name -> [list of post files/IDs]

### Step 2: Health Checks

| Check | Threshold | Action |
|-------|-----------|--------|
| Thin tag archives | < 5 posts per tag | Review for merge or noindex after traffic, intent, and link checks |
| Orphan tags | 0 posts | Recommend deletion |
| Tag bloat | More than `max(50, post_count * 0.25)` total tags, adjusted for taxonomy purpose | Recommend consolidation |
| Category depth | > 3 levels | Recommend flattening |
| Uncategorized posts | No category assigned | Assign to appropriate category |
| Duplicate slugs | Same slug, different name | Merge into canonical version |

### Step 3: Recommendations

Group findings by priority:
- **Critical**: orphan tags creating empty archive pages (crawl waste)
- **High**: thin tags with < 5 posts after traffic, intent, and link checks
- **Medium**: tag bloat above the scaled threshold (diluted taxonomy, harder to navigate)
- **Low**: naming inconsistencies (mixed case, hyphen vs space)

### Output Format

```
## Taxonomy Audit: [Site/Directory]

**Total tags**: [n] | **Total categories**: [n]
**Healthy**: [n] | **Thin**: [n] | **Orphan**: [n]

### Critical Issues
- [orphan tags list]

### Recommendations
1. Merge [tag-a] and [tag-b] (same topic, [n] combined posts)
2. Delete orphan tags: [list]
3. Merge or noindex tag archives with < 5 posts only after traffic, intent, and link checks
```

## Site-Wide Guidelines

- Aim for 5-10 main categories per site (broad topics)
- Tags should have at least 5 posts before creating an archive page
- Use consistent slug format: lowercase, hyphen-separated
- Every post needs exactly 1 primary category
- Tags per post: 3-8 recommended, never exceed 15

## Handoff Inputs

Provide the target CMS name, a local content/taxonomy export when auditing
existing state, and an optional public site URL for identifiers. Do not provide
API keys, passwords, cookies, OAuth tokens, or other CMS credentials. Write the
handoff under the current article/run output and mark `publish_performed: false`.

## Error Handling

- **Missing target**: If the CMS type is absent, list the five supported handoff formats
- **Missing inventory**: Generate suggestions, but label deduplication against live taxonomy as unavailable
- **Duplicate tag slugs**: Deduplicate within the supplied local inventory and record each merge
- **Unsupported CMS**: If CMS_TYPE is not one of the 5 supported platforms, list the valid options and exit
