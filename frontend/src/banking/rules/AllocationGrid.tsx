"use client";

/**
 * Allocation grid of a bank rule (F-04-T12): where the money goes. Each line has an account, a
 * description, a tax code — **filtered by the rule's type**: purchase codes for spend rules,
 * sales codes for receive rules — and either a percentage or a fixed amount. Fixed lines are
 * taken first and the percentages share the rest, so they must total **100 %**: the running
 * total turns green at exactly 100 % and red otherwise, and the builder's Save stays disabled
 * until it does (``allocationsValid``). Rounding goes to the last percentage line (server).
 */
import { Button, INPUT_BASE, Input } from "@numo9/ui";
import { useId } from "react";

import type { Account } from "@/accounts/api";
import { useFormatMessage } from "@/i18n";
import type { TaxCode } from "@/tax/api";

import type { RuleType } from "./api";
import { allocation as am } from "./allocationMessages";
import { emptyAllocation, type AllocationRow } from "./draft";

const SCALE = 10_000;
const HUNDRED = 100 * SCALE;

function units(value: string): number | null {
  const text = value.trim().replace(",", ".");
  if (!/^\d+(\.\d{1,4})?$/.test(text)) return null;
  return Math.round(Number(text) * SCALE);
}

/** The percentage lines' total in ten-thousandths of a percent (null when a value is invalid). */
export function percentTotal(rows: AllocationRow[]): number | null {
  let total = 0;
  for (const row of rows) {
    if (row.mode !== "percent") continue;
    const value = units(row.value);
    if (value === null) return null;
    total += value;
  }
  return total;
}

export function allocationsValid(rows: AllocationRow[]): boolean {
  if (!rows.length) return false;
  for (const row of rows) {
    const value = units(row.value);
    if (!row.account || value === null || value <= 0) return false;
    if (row.mode === "percent" && value > HUNDRED) return false;
  }
  const percent = rows.some((r) => r.mode === "percent");
  return !percent || percentTotal(rows) === HUNDRED;
}

function shown(total: number): string {
  return (total / SCALE).toLocaleString("en-CA", { maximumFractionDigits: 4 });
}

export interface AllocationGridProps {
  type: RuleType;
  rows: AllocationRow[];
  accounts: Account[];
  taxCodes: TaxCode[];
  onChange: (rows: AllocationRow[]) => void;
}

export function AllocationGrid({ type, rows, accounts, taxCodes, onChange }: AllocationGridProps) {
  const fm = useFormatMessage();
  const id = useId();
  const side = type === "receive" ? "sales" : "purchase";
  const codes = taxCodes.filter((c) => c.side === side && !c.archived_at && !c.expired);
  const lineAccounts = accounts.filter((a) => !a.is_bank);
  const total = percentTotal(rows);
  const hasPercent = rows.some((r) => r.mode === "percent");
  const valid = allocationsValid(rows);

  function update(index: number, changes: Partial<AllocationRow>) {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...changes } : row)));
  }

  return (
    <section className="flex flex-col gap-3" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="text-lg font-semibold text-fg">
        {fm(am.title)}
      </h2>
      <p className="text-sm text-fg-muted">{fm(am.intro)}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] border-collapse text-sm">
          <thead>
            <tr className="text-left text-fg-muted">
              <th className="p-2 font-semibold">{fm(am.account)}</th>
              <th className="p-2 font-semibold">{fm(am.description)}</th>
              <th className="p-2 font-semibold">{fm(am.taxCode)}</th>
              <th className="p-2 font-semibold">{fm(am.share)}</th>
              <th className="p-2 text-right font-semibold">{fm(am.value)}</th>
              <th className="p-2">
                <span className="sr-only">{fm(am.actions)}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const number = index + 1;
              return (
                <tr key={index} className="border-t border-border" data-allocation={index}>
                  <td className="p-2">
                    <select
                      aria-label={fm(am.accountLabel, { number })}
                      className={INPUT_BASE}
                      value={row.account}
                      onChange={(e) => update(index, { account: e.target.value })}
                    >
                      <option value="" />
                      {lineAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {fm(am.accountOption, { code: a.code, name: a.name })}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="p-2">
                    <Input
                      aria-label={fm(am.descriptionLabel, { number })}
                      value={row.description}
                      onChange={(e) => update(index, { description: e.target.value })}
                    />
                  </td>
                  <td className="p-2">
                    <select
                      aria-label={fm(am.taxLabel, { number })}
                      className={INPUT_BASE}
                      value={row.tax_code}
                      onChange={(e) => update(index, { tax_code: e.target.value })}
                    >
                      <option value="">{fm(am.noTax)}</option>
                      {codes.map((c) => (
                        <option key={c.id} value={c.code}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="p-2">
                    <select
                      aria-label={fm(am.shareLabel, { number })}
                      className={INPUT_BASE}
                      value={row.mode}
                      onChange={(e) =>
                        update(index, { mode: e.target.value as AllocationRow["mode"] })
                      }
                    >
                      <option value="percent">{fm(am.percent)}</option>
                      <option value="fixed">{fm(am.fixed)}</option>
                    </select>
                  </td>
                  <td className="p-2">
                    <Input
                      aria-label={fm(row.mode === "percent" ? am.percentLabel : am.amountLabel, {
                        number,
                      })}
                      inputMode="decimal"
                      numeric
                      suffix={row.mode === "percent" ? "%" : undefined}
                      prefix={row.mode === "fixed" ? "$" : undefined}
                      value={row.value}
                      onChange={(e) => update(index, { value: e.target.value })}
                    />
                  </td>
                  <td className="p-2 text-right">
                    {rows.length > 1 ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onChange(rows.filter((_r, i) => i !== index))}
                      >
                        {fm(am.remove, { number })}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onChange([...rows, { ...emptyAllocation(), value: "" }])}
        >
          {fm(am.addLine)}
        </Button>
        <p
          role="status"
          data-total=""
          data-valid={valid ? "true" : "false"}
          className={`text-sm font-semibold ${valid ? "text-fg-success" : "text-fg-danger"}`}
        >
          {hasPercent
            ? total === null
              ? fm(am.totalInvalid)
              : fm(valid ? am.totalOk : am.totalOff, { total: shown(total) })
            : rows.length
              ? fm(am.fixedOnly)
              : fm(am.none)}
        </p>
      </div>
    </section>
  );
}
