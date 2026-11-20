# Search and command palette (A-09)

**Index.** One `search_searchdocument` row per searchable record (organisation, type, id): title,
subtitle, code, body, amount, date, link, the permission and package feature needed to see it,
and a PostgreSQL search vector (`simple` + `unaccent`; title A, code and subtitle B, body C) with
trigram indexes on title and code. Row-level security keeps it per organisation.

**Providers.** A searchable model registers `to_document()` (`numo9/search/registry.py`); saves
and deletes update its document in the same transaction. Phase 0 providers: contacts (and their
people), accounts, journals (narration and line descriptions), the organisation, its users,
documents.

**API.** `GET /api/v1/o/<org>/search?q=…` — records, settings, reports, navigation. Results the
user may not see are left out; results the package lacks stay, locked, with the reason.

**Palette.** Ctrl/⌘+K in an organisation (`frontend/src/search`): Recent, Create, Records,
Settings, Reports, Go to. `?` opens the shortcut sheet; `N` then a letter opens a quick-create
action:

| Keys | Action |
| ---- | ------ |
| N I | New invoice |
| N B | New bill |
| N C | New contact |
| N Q | New quote |
| N P | New purchase order |
| N J | New manual journal |
| N S | Spend money |
| N R | Receive money |
| N T | Transfer money |
| N U | Invite a user |

## Drift: rebuild and check

```bash
python manage.py reindex_search --org <organisation public id>   # rebuild one organisation
python manage.py reindex_search                                  # rebuild all
python manage.py reindex_search --check                          # report only; exits 1 on drift
```

A rebuild writes every searchable record's document and removes documents with no record
behind them; run `--check` nightly and rebuild the organisations it reports.
