"use client";

/**
 * Find & recode (C-07-T10 – T13), `/o/:org/accounting/recode`: two panes — the conditions on
 * the left (condition builder, C-07-T10), the lines found on the right (results grid with
 * select-all across pages and the Excluded tab, C-07-T11).
 */
import { Button } from "@numo9/ui";
import { useCallback, useEffect, useState } from "react";

import { accountsApi } from "@/accounts/api";
import { useFormatMessage } from "@/i18n";

import { recodeApi, type Criteria, type Match, type SearchResult } from "./api";
import { ConditionBuilder, type AccountOption } from "./ConditionBuilder";
import { emptyRows, newRow, serialise, type Row } from "./conditions";
import { rm } from "./messages";
import { RecodeResults } from "./RecodeResults";

export function RecodeScreen({ org }: { org: string }) {
  const fm = useFormatMessage();
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [match, setMatch] = useState<Match>("all");
  const [rows, setRows] = useState<Row[]>(() => [newRow("account")]);
  const [invalid, setInvalid] = useState<string[]>([]);
  const [criteria, setCriteria] = useState<Criteria | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void accountsApi
      .list(org, "active")
      .then((answer) => {
        if (answer.status === 200) {
          setAccounts(
            answer.body.results.map((a) => ({ id: a.id, label: `${a.code} · ${a.name}` })),
          );
        }
      })
      .catch(() => undefined);
  }, [org]);

  const run = useCallback(
    async (search: Criteria, page: number) => {
      setBusy(true);
      setError("");
      const answer = await recodeApi.search(org, search, page).catch(() => null);
      setBusy(false);
      if (answer?.status === 200) {
        setResult(answer.body);
        return true;
      }
      setError(answer?.body?.detail || fm(rm.failed));
      return false;
    },
    [org, fm],
  );

  const search = async () => {
    const missing = emptyRows(rows);
    setInvalid(missing);
    if (missing.length) return;
    const next = serialise(match, rows);
    setCriteria(next);
    setSelected(new Set());
    await run(next, 1);
  };

  return (
    <div className="flex flex-col gap-4" data-recode="">
      <header>
        <h1 className="text-xl font-semibold text-fg">{fm(rm.title)}</h1>
        <p className="max-w-3xl text-sm text-fg-muted">{fm(rm.intro)}</p>
      </header>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <div className="flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full flex-col gap-3 lg:w-96 lg:shrink-0">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void search();
            }}
            className="flex flex-col gap-3"
          >
            <ConditionBuilder
              match={match}
              rows={rows}
              accounts={accounts}
              onMatchChange={setMatch}
              onRowsChange={setRows}
              invalid={invalid}
            />
            <div>
              <Button type="submit" variant="primary" disabled={busy}>
                {fm(rm.search)}
              </Button>
            </div>
          </form>
        </aside>
        <section className="flex min-w-0 flex-1 flex-col gap-4">
          {result && criteria ? (
            <RecodeResults
              result={result}
              selected={selected}
              onSelectedChange={setSelected}
              onPage={(page) => void run(criteria, page)}
            />
          ) : null}
        </section>
      </div>
    </div>
  );
}
