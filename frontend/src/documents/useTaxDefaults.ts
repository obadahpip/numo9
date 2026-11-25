"use client";

/**
 * Default tax codes in a document editor (G-02-T07): the server's resolver (`POST tax/resolve`)
 * picks each line's code from the contact, the document date, the line's account and item. A
 * line keeps its default — and shows the **auto** chip with the reason as its tooltip — until
 * the person picks another code: then it is **overridden** (the dot), is never re-resolved, and
 * the dot resets it to the default. Changing the contact or the date re-resolves only the lines
 * that aren't overridden. Inline warnings (`tax.pos.pst_unregistered`, …) come back per line.
 */
import type { DocumentGridLine } from "@numo9/ui";
import { useEffect, useMemo, useRef, useState } from "react";

import { apiRequest } from "@/auth/client";
import { useFormatMessage } from "@/i18n";
import { explain } from "@/tax/explanations";

export const RESOLVE_DEBOUNCE_MS = 250;

export interface ResolvedLine {
  key: string;
  tax_code: { id: string; code: string; name: string; version: number } | null;
  source: string;
  auto: boolean;
  explanation: string;
  params: Record<string, unknown>;
  province: string;
  flags: string[];
  warnings: string[];
}

export interface TaxDefaultsInput {
  org: string;
  side: "sales" | "purchase";
  date: string;
  contact: string | null;
  lines: readonly DocumentGridLine[];
  setLines: (update: (lines: DocumentGridLine[]) => DocumentGridLine[]) => void;
  /** False for a posted (read-only) document: nothing is resolved or changed. */
  enabled?: boolean;
  /** False: resolve for the warnings only, never change a line's code (an editor with its own
   * defaults, e.g. spend / receive money). */
  apply?: boolean;
}

/** An inline tax warning of the editor (G-02-T08): its key, the lines (1-based) and params. */
export interface TaxNotice {
  code: "tax.pos.pst_unregistered" | "missing_province";
  lines: number[];
  province: string;
}

export interface TaxDefaults {
  taxWhy: Record<string, string>;
  taxAuto: Record<string, boolean>;
  taxOverridden: Record<string, boolean>;
  reset: (lineId: string) => void;
  /** Per line id, the resolver's warning keys. */
  warnings: Record<string, string[]>;
  /** Per line id, the resolver's flags (`missing_province`). */
  flags: Record<string, string[]>;
  /** The inline warnings, grouped (G-02-T08). */
  notices: TaxNotice[];
}

export function resolveTax(
  org: string,
  body: {
    side: string;
    date: string;
    contact: string | null;
    lines: { account: string | null; item: string | null }[];
  },
) {
  return apiRequest<{ lines: ResolvedLine[] }>(`/api/v1/o/${encodeURIComponent(org)}/tax/resolve`, {
    method: "POST",
    body,
  });
}

export function useTaxDefaults({
  org,
  side,
  date,
  contact,
  lines,
  setLines,
  enabled = true,
  apply = true,
}: TaxDefaultsInput): TaxDefaults {
  const fm = useFormatMessage();
  const [resolved, setResolved] = useState<Record<string, ResolvedLine>>({});
  /** The code each line got from the resolver (what "not overridden" means). */
  const defaults = useRef<Record<string, string | null>>({});
  const asked = useRef(0);
  const key = JSON.stringify([
    side,
    date,
    contact,
    lines.map((l) => [l.id, l.account, l.item || null]),
  ]);

  useEffect(() => {
    if (!enabled || !date) return;
    const ask = ++asked.current;
    const snapshot = lines.map((l) => ({ id: l.id, account: l.account, item: l.item || null }));
    const timer = setTimeout(() => {
      void resolveTax(org, {
        side,
        date,
        contact,
        lines: snapshot.map(({ account, item }) => ({ account, item })),
      })
        .then((answer) => {
          if (ask !== asked.current || answer.status !== 200) return;
          const next: Record<string, ResolvedLine> = {};
          snapshot.forEach((line, i) => {
            const found = answer.body.lines[i];
            if (found) next[line.id] = found;
          });
          if (apply)
            setLines((current) =>
              current.map((line) => {
                const found = next[line.id];
                if (!found) return line;
                const before = defaults.current[line.id];
                const untouched = line.taxCode === null || line.taxCode === (before ?? null);
                defaults.current[line.id] = found.tax_code?.id ?? null;
                return untouched && found.tax_code && line.taxCode !== found.tax_code.id
                  ? { ...line, taxCode: found.tax_code.id }
                  : line;
              }),
            );
          setResolved(next);
        })
        .catch(() => undefined);
    }, RESOLVE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
    // `key` stands for the inputs that change the defaults (not the chosen codes).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, org, enabled, apply]);

  return useMemo(() => {
    const taxWhy: Record<string, string> = {};
    const taxAuto: Record<string, boolean> = {};
    const taxOverridden: Record<string, boolean> = {};
    const warnings: Record<string, string[]> = {};
    const flags: Record<string, string[]> = {};
    for (const line of lines) {
      const found = resolved[line.id];
      if (!found) continue;
      const code = found.tax_code?.id ?? null;
      warnings[line.id] = found.warnings;
      flags[line.id] = found.flags;
      if (line.taxCode !== null && code !== null && line.taxCode !== code) {
        taxOverridden[line.id] = true;
      } else if (code !== null && line.taxCode === code) {
        taxAuto[line.id] = true;
        const why = explain(fm, found.explanation, found.params);
        if (why) taxWhy[line.id] = why;
      }
    }
    const notices: TaxNotice[] = [];
    const add = (code: TaxNotice["code"], line: number, province: string) => {
      const found = notices.find((n) => n.code === code && n.province === province);
      if (found) found.lines.push(line);
      else notices.push({ code, lines: [line], province });
    };
    lines.forEach((line, index) => {
      const found = resolved[line.id];
      if (!found) return;
      if (found.warnings.includes("tax.pos.pst_unregistered")) {
        add("tax.pos.pst_unregistered", index + 1, found.province);
      }
      if (found.flags.includes("missing_province")) add("missing_province", index + 1, "");
    });
    const reset = (lineId: string) => {
      const code = resolved[lineId]?.tax_code?.id;
      if (!code) return;
      setLines((current) => current.map((l) => (l.id === lineId ? { ...l, taxCode: code } : l)));
    };
    if (!apply) {
      return { taxWhy: {}, taxAuto: {}, taxOverridden: {}, reset, warnings, flags, notices };
    }
    return { taxWhy, taxAuto, taxOverridden, reset, warnings, flags, notices };
  }, [lines, resolved, fm, setLines, apply]);
}
