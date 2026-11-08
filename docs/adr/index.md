# Architecture decision records

An ADR records one significant decision: the context, the options considered, the choice and its
consequences. ADRs follow [MADR](https://adr.github.io/madr/) and live in `docs/adr/`.

## When to write one

- Choosing or replacing a technology, provider or hosting region.
- A decision that is expensive to reverse (data model, tenancy, money type, posting engine).
- A decision the client must sign off (for example ADR-001 hosting and data residency).

## How

1. Copy [the template](template.md) to `docs/adr/NNNN-short-title.md` (next free number, kebab-case).
2. Fill it in; status starts as `proposed`.
3. Add it to the `nav` in `mkdocs.yml` and to the list below.
4. Open a PR (`docs/<ID>-adr-short-title`). When it is merged, status becomes `accepted`.
5. Never edit an accepted ADR's decision; supersede it with a new ADR and link both ways.

## Decisions

| ADR | Title | Status |
|---|---|---|
| [ADR-0001](0001-hosting-and-data-residency.md) | Host Numo9 on AWS Canada (Central) with Canada (West) for backups (S-02-T01) | superseded by ADR-0002 |
| [ADR-0002](0002-hetzner-helsinki-hosting.md) | Host Numo9 on Hetzner Cloud in Helsinki (supersedes ADR-0001) | accepted (2026-11-08) |
