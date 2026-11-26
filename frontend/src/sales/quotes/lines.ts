/**
 * Quote lines in the editor (D-02-T12): the shared grid's lines plus the quote's own fields —
 * `isOptional` (the customer may tick it), `alternativeGroup` (lines of a group are alternatives,
 * the customer chooses one) and `selected`. The same rule as the server (`quotes.counted`,
 * D-02-T03) decides which lines count in the totals.
 */
import { newDocumentLine, parseLineDiscount, type DocumentGridLine } from "@numo9/ui";

import type { QuoteLine, QuoteLineInput } from "./api";

export interface QuoteGridLine extends DocumentGridLine {
  isOptional?: boolean;
  alternativeGroup?: string;
  selected?: boolean;
}

export function newQuoteLine(): QuoteGridLine {
  return { ...newDocumentLine(), isOptional: false, alternativeGroup: "", selected: true };
}

export function quoteGridLine(line: QuoteLine): QuoteGridLine {
  const value = Number(line.discount_value);
  return {
    ...newDocumentLine(),
    id: line.id,
    description: line.description,
    quantity: String(Number(line.quantity)),
    unitPrice: String(Number(line.unit_price).toFixed(2)),
    discount:
      line.discount_type === "percent"
        ? `${value}%`
        : line.discount_type === "amount"
          ? value.toFixed(2)
          : "",
    account: line.account?.id ?? null,
    taxCode: line.tax_code?.id ?? null,
    isOptional: line.is_optional,
    alternativeGroup: line.alternative_group,
    selected: line.selected,
  };
}

/**
 * Which lines count, in order: a plain line always; an optional line when selected; of an
 * alternative group the first selected line (none selected: the group adds nothing).
 */
export function countedLines(lines: readonly QuoteGridLine[]): boolean[] {
  const chosen = new Set<string>();
  return lines.map((line) => {
    const group = (line.alternativeGroup ?? "").trim();
    if (group) {
      const take = line.selected !== false && !chosen.has(group);
      if (take) chosen.add(group);
      return take;
    }
    if (line.isOptional) return Boolean(line.selected);
    return true;
  });
}

/**
 * The lines after an edit, kept consistent: a line in a group isn't optional; a line newly made
 * optional starts unticked (as the customer first sees it); choosing one alternative of a group
 * unticks the others; a group always has at most one selected line.
 */
export function normaliseQuoteLines(
  next: readonly QuoteGridLine[],
  before: readonly QuoteGridLine[],
): QuoteGridLine[] {
  const previous = new Map(before.map((line) => [line.id, line]));
  const lines = next.map((line) => {
    const old = previous.get(line.id);
    const group = (line.alternativeGroup ?? "").trim();
    const isOptional = group ? false : Boolean(line.isOptional);
    let selected = line.selected ?? true;
    if (isOptional && !old?.isOptional) selected = false;
    if (!isOptional && !group) selected = true;
    return { ...line, isOptional, alternativeGroup: group, selected };
  });
  // The alternative the person just ticked wins; otherwise the first selected one stays.
  const ticked = new Map<string, string>();
  for (const line of lines) {
    const group = line.alternativeGroup ?? "";
    const old = previous.get(line.id);
    if (group && line.selected && old && old.selected === false) ticked.set(group, line.id);
  }
  const kept = new Map<string, string>();
  return lines.map((line) => {
    const group = line.alternativeGroup ?? "";
    if (!group || !line.selected) return line;
    const winner = ticked.get(group) ?? kept.get(group) ?? line.id;
    kept.set(group, winner);
    return winner === line.id ? line : { ...line, selected: false };
  });
}

/** The alternative groups used, in order of first use (the picker's choices). */
export function alternativeGroups(lines: readonly QuoteGridLine[]): string[] {
  return [...new Set(lines.map((l) => (l.alternativeGroup ?? "").trim()).filter(Boolean))];
}

/** The lines the server receives: every line with something on it. */
export function quoteLines(
  lines: readonly QuoteGridLine[],
  overridden: (id: string) => boolean = () => false,
): QuoteLineInput[] {
  return lines
    .filter((line) => line.description || Number(line.unitPrice) > 0)
    .map((line) => {
      const discount = parseLineDiscount(line.discount) ?? { type: "none" as const, value: "0" };
      return {
        description: line.description,
        quantity: line.quantity || "1",
        unit_price: line.unitPrice || "0",
        discount_type: discount.type,
        discount_value: discount.value,
        account: line.account,
        tax_code: line.taxCode,
        tax_overridden: overridden(line.id),
        is_optional: Boolean(line.isOptional),
        alternative_group: (line.alternativeGroup ?? "").trim(),
        selected: line.selected !== false,
      };
    });
}
