# Search and command palette (A-09)

**Index.** One `search_searchdocument` row per searchable record (organisation, type, id): title,
subtitle, code, body, amount, date, link, the permission and package feature needed to see it,
and a PostgreSQL search vector (`simple` + `unaccent`; title A, code and subtitle B, body C) with
trigram indexes on title and code. Row-level security keeps it per organisation.

**Providers.** A searchable model registers `to_document()` (`numo9/search/registry.py`); saves
and deletes update its document in the same transaction. Phase 0 providers: contacts (and their
people), accounts, journals (narration and line descriptions), the organisation, its users,
documents. Phase 1 adds bank accounts (name, institution, type, ledger code — "petty" finds Petty
Cash) and spend / receive money (reference, contact, line descriptions), registered by
`numo9/banking/search.py` (F-01-T13).

**API.** `GET /api/v1/o/<org>/search?q=…` — records, settings, reports, navigation. Results the
user may not see are left out; results the package lacks stay, locked, with the reason.

**Palette.** Ctrl/⌘+K in an organisation (`frontend/src/search`): Recent, Create, Records,
Settings, Reports, Go to. `?` opens the shortcut sheet; `N` then a letter opens a quick-create
action; the top bar's **+** menu lists the same actions with their shortcuts:

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
| N A | Add bank account |
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

## Performance: p95 < 150 ms at a million documents (A-09-T10)

Each tier reads an index and stops early:

- **codes** — `upper(code::text) COLLATE "C"` (migration 0002): equality and a prefix range,
  already in code order;
- **amounts** — `(organisation_id, amount)`;
- **words** — the search-vector GIN index; ranked among the first 2,000 matches only (a two-letter
  prefix can match a third of the index);
- **typos** — only when the exact tiers left room and the query has no digits:
  `title %>> query` (strict word similarity, trigram GIN index), the first 500 candidates, within
  a 60 ms statement budget — past it the typo tier is dropped, never the request.

```bash
python manage.py seed_search --docs 1000000 --password "$SEED_PASSWORD"   # dev/staging only
k6 run -e PASSWORD="$SEED_PASSWORD" tools/perf/k6/search.js               # or: make perf-search
```

`backend/tests/test_search_performance.py` runs the same queries over 200,000 documents in CI.
Measured on the development machine with 1,000,000 documents: p95 110 ms through the Django
stack (single client), slowest queries the multi-word typos.
