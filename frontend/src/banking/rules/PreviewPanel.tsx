"use client";

/**
 * History preview panel (F-04-T13): "test against history". Runs the rule being built — saved
 * or not — against the uncoded statement lines of the last 90 days (the preview endpoint,
 * F-04-T08; nothing is written) and lists the **affected lines**: the ones this rule would code
 * (with the lower-priority rules it shadows on them) and the ones a higher-priority rule takes,
 * naming that **shadowing rule** ("Shadowed by Fuel — all stations"). It re-runs on its own a
 * moment after the conditions change, and on **Run the test**.
 */
import { Button, formatDate, formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { rulesApi, type PreviewResult, type RuleInput, type RuleRefusal } from "./api";
import { preview as pm } from "./previewMessages";

const TIME_ZONE = "America/Toronto";
export const PREVIEW_DAYS = 90;

export interface PreviewPanelProps {
  org: string;
  rule: RuleInput;
  /** The saved rule being edited: its own priority is used and it isn't counted twice. */
  ruleId?: string | null;
  /** The conditions are complete (otherwise nothing is sent). */
  ready: boolean;
  /** Wait after the last change before re-running (ms). */
  delay?: number;
}

export function PreviewPanel({ org, rule, ruleId, ready, delay = 600 }: PreviewPanelProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const id = useId();
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [refusal, setRefusal] = useState<RuleRefusal | null>(null);
  const [busy, setBusy] = useState(false);
  const run = useRef(0);
  // Only what the preview depends on (conditions, type, scope) re-runs it.
  const key = JSON.stringify({
    type: rule.type,
    match_mode: rule.match_mode,
    conditions: rule.conditions,
    scope: rule.scope_accounts ?? [],
  });

  async function test() {
    const mine = ++run.current;
    setBusy(true);
    const body: RuleInput = { ...rule, allocations: [], name: rule.name };
    const answer = await rulesApi
      .preview(org, body, { id: ruleId, days: PREVIEW_DAYS })
      .catch(() => null);
    if (mine !== run.current) return;
    setBusy(false);
    if (answer?.status === 200 && Array.isArray(answer.body?.rows)) {
      setResult(answer.body);
      setRefusal(null);
    } else {
      setResult(null);
      setRefusal(
        answer && typeof answer.body === "object" && answer.body
          ? (answer.body as RuleRefusal)
          : { detail: fm(pm.failed) },
      );
    }
  }

  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(() => void test(), delay);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-run when the rule's key changes
  }, [key, ready, delay]);

  const money = (amount: string) => formatMoney(amount, { locale, currency: "CAD" });

  return (
    <section
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface-subtle p-4"
      aria-labelledby={`${id}-title`}
      data-preview=""
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${id}-title`} className="text-lg font-semibold text-fg">
          {fm(pm.title)}
        </h2>
        <Button variant="secondary" size="sm" disabled={!ready || busy} onClick={() => void test()}>
          {fm(pm.refresh)}
        </Button>
      </div>
      <p className="text-sm text-fg-muted">{fm(pm.intro, { days: PREVIEW_DAYS })}</p>
      <div role="status" aria-live="polite" className="text-sm text-fg">
        {!ready ? (
          fm(pm.incomplete)
        ) : busy ? (
          fm(pm.running)
        ) : refusal ? (
          <span className="font-semibold text-fg-danger">{refusal.detail ?? fm(pm.failed)}</span>
        ) : result ? (
          result.rows.length ? (
            fm(pm.summary, { applies: result.applies, shadowed: result.shadowed })
          ) : (
            fm(pm.none, { days: result.days })
          )
        ) : null}
      </div>
      {ready && result && result.rows.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] border-collapse text-sm">
            <thead>
              <tr className="text-left text-fg-muted">
                <th className="p-2 font-semibold">{fm(pm.date)}</th>
                <th className="p-2 font-semibold">{fm(pm.line)}</th>
                <th className="p-2 text-right font-semibold">{fm(pm.amount)}</th>
                <th className="p-2 font-semibold">{fm(pm.outcome)}</th>
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row) => (
                <tr
                  key={row.line.id}
                  className="border-t border-border align-top"
                  data-outcome={row.outcome}
                >
                  <td className="p-2 whitespace-nowrap">
                    {formatDate(row.line.date, { locale, timeZone: TIME_ZONE })}
                  </td>
                  <td className="p-2">
                    <span className="block text-fg">{row.line.description || row.line.payee}</span>
                    <span className="block text-xs text-fg-muted">
                      {row.line.bank_account.name}
                    </span>
                  </td>
                  <td className="p-2 text-right tabular-nums">{money(row.line.amount)}</td>
                  <td className="p-2">
                    {row.outcome === "applies" ? (
                      <>
                        <span className="font-semibold text-fg-success">{fm(pm.applies)}</span>
                        {row.also_matches.length ? (
                          <span className="block text-xs text-fg-muted">
                            {fm(pm.alsoMatches, {
                              names: row.also_matches.map((r) => r.name).join(", "),
                            })}
                          </span>
                        ) : null}
                      </>
                    ) : (
                      <span className="font-semibold text-fg-warning">
                        {fm(pm.shadowedBy, { name: row.shadowed_by?.name ?? "" })}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.truncated ? <p className="text-xs text-fg-muted">{fm(pm.truncated)}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
