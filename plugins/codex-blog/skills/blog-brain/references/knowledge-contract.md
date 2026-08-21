# Blog Brain Knowledge Contract

Each entry is a small Markdown or JSON record addressable by a stable ID. The
store index may be rebuilt from entries, so entries remain the source of truth.

## Entry fields

- `id`: stable, opaque identifier.
- `type`: `fact`, `audience`, `voice`, `terminology`, `internal-link`,
  `decision`, `experiment`, `lesson`, or `hypothesis`.
- `statement`: the minimal reusable claim or preference.
- `fact_state`: `verified`, `supported`, `unverified`, `contradicted`, or
  `not-applicable`.
- `publication`: `public`, `internal`, `private`, or `do-not-publish`.
- `source_refs`: file paths/URLs and relevant source record identifiers.
- `scope`: `project` or `global`.
- `created_at`, `reviewed_at`, and optional `expires_at`.
- `supersedes` and `superseded_by` for non-destructive history.
- optional `topics`, `entities`, `locale`, and `notes`.

## Invariants

1. Every factual entry has provenance or remains `unverified`.
2. Promotion copies an entry and records origin; it does not remove the project
   entry.
3. Superseding preserves both records and makes the active relationship clear.
4. Retrieval never exposes entries outside their publication boundary.
5. The index contains no secrets or full source documents.
6. Deletion targets one resolved ID and scope, never a wildcard or broad store.

## Retrieval ranking

Prefer exact named-entity/topic matches, then locale/audience matches, then
recently reviewed project entries, then global defaults. Lower-ranked entries
may fill context but cannot silently override a higher-precedence input.

## Corruption handling

Validate an entry before indexing it. Quarantine an invalid record by reporting
its path; do not rewrite it automatically. If the index is invalid but entries
are readable, build an in-memory index for the current request and offer a
separate repair action.
