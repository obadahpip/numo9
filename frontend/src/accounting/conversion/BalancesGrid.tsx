"use client";

/**
 * Opening balances grid (C-05-T10): one row per account — account, debit or credit (typing one
 * side clears the other), description. Used by the Bank and cash step (bank accounts only) and
 * the Other balances step (every other account). Rows the server refused are flagged with their
 * message.
 */
import { AccountPicker, Button, IconButton, Input, type PickerAccount } from "@numo9/ui";
import { CloseIcon } from "@numo9/ui";

import { useDocumentLinesLabels } from "@/documents/labels";
import { useFormatMessage } from "@/i18n";

import { cm } from "./messages";

export interface BalanceRow {
  key: string;
  account: string;
  debit: string;
  credit: string;
  description: string;
}

let seq = 0;
export function newBalanceRow(account = ""): BalanceRow {
  seq += 1;
  return { key: `row-${seq}`, account, debit: "", credit: "", description: "" };
}

export interface BalancesGridProps {
  rows: BalanceRow[];
  onChange: (rows: BalanceRow[]) => void;
  accounts: readonly PickerAccount[];
  /** Problems per row index (0-based) from the last save. */
  problems?: Record<number, string>;
  readOnly?: boolean;
  name: string;
}

export function BalancesGrid({
  rows,
  onChange,
  accounts,
  problems = {},
  readOnly = false,
  name,
}: BalancesGridProps) {
  const fm = useFormatMessage();
  const { accountTypes, noAccounts } = useDocumentLinesLabels();
  const set = (index: number, change: Partial<BalanceRow>) =>
    onChange(rows.map((row, i) => (i === index ? { ...row, ...change } : row)));

  return (
    <div className="flex flex-col gap-2">
      <table className="w-full text-sm" data-balances={name}>
        <thead>
          <tr className="text-xs text-fg-muted">
            <th scope="col" className="w-2/5 py-1 text-start">
              {fm(cm.account)}
            </th>
            <th scope="col" className="py-1 text-end">
              {fm(cm.debit)}
            </th>
            <th scope="col" className="py-1 text-end">
              {fm(cm.credit)}
            </th>
            <th scope="col" className="py-1 text-start">
              {fm(cm.description)}
            </th>
            <th scope="col" className="w-10">
              <span className="sr-only">{fm(cm.removeLine, { line: "" })}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const n = index + 1;
            const problem = problems[index];
            return (
              <tr
                key={row.key}
                data-line={n}
                data-invalid={problem ? "" : undefined}
                className="border-t border-border align-top"
              >
                <td className="py-2 pe-2">
                  <AccountPicker
                    aria-label={fm(cm.accountOfLine, { line: n })}
                    accounts={accounts}
                    value={row.account || null}
                    onChange={(id) => set(index, { account: id ?? "" })}
                    typeLabels={accountTypes}
                    emptyMessage={noAccounts}
                    placeholder={fm(cm.chooseAccount)}
                    disabled={readOnly}
                  />
                  {problem ? (
                    <p role="alert" className="mt-1 text-xs text-fg-danger">
                      {fm(cm.rowProblem, { line: n, message: problem })}
                    </p>
                  ) : null}
                </td>
                <td className="py-2 pe-2">
                  <Input
                    numeric
                    inputMode="decimal"
                    aria-label={fm(cm.debitOfLine, { line: n })}
                    value={row.debit}
                    disabled={readOnly}
                    onChange={(e) => set(index, { debit: e.target.value, credit: "" })}
                  />
                </td>
                <td className="py-2 pe-2">
                  <Input
                    numeric
                    inputMode="decimal"
                    aria-label={fm(cm.creditOfLine, { line: n })}
                    value={row.credit}
                    disabled={readOnly}
                    onChange={(e) => set(index, { credit: e.target.value, debit: "" })}
                  />
                </td>
                <td className="py-2 pe-2">
                  <Input
                    aria-label={fm(cm.descriptionOfLine, { line: n })}
                    value={row.description}
                    disabled={readOnly}
                    onChange={(e) => set(index, { description: e.target.value })}
                  />
                </td>
                <td className="py-2">
                  {readOnly ? null : (
                    <IconButton
                      label={fm(cm.removeLine, { line: n })}
                      icon={<CloseIcon />}
                      variant="ghost"
                      onClick={() => onChange(rows.filter((_, i) => i !== index))}
                    />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {readOnly ? null : (
        <div>
          <Button variant="secondary" onClick={() => onChange([...rows, newBalanceRow()])}>
            {fm(cm.addLine)}
          </Button>
        </div>
      )}
    </div>
  );
}
