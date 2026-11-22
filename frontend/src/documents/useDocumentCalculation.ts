"use client";

/**
 * Live document figures (D-01-T14): the client mirror's result at once, the server's after a
 * short pause in typing (debounced). The server's result wins whenever it is the answer to the
 * latest input; an older answer is ignored. Problems (D-01-T06) come from the server.
 */
import type { DocumentGridLine, DocumentLineAmounts, DocumentTotalsValue } from "@numo9/ui";
import { parseLineDiscount } from "@numo9/ui";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  documentsApi,
  type CalculateRequest,
  type CalculateResponse,
  type DocumentSide,
  type LineProblem,
} from "./api";
import { calculateDocument, type DiscountType, type DocResult, type TaxMode } from "./calculator";

export const DEBOUNCE_MS = 300;

/** What the mirror needs to know about a tax code version: its components. */
export interface MirrorTaxCode {
  id: string;
  components: { key: string; name: string; rate: string; claimable_pct?: string }[];
}

export interface DocumentCalculationInput {
  org: string;
  side: DocumentSide;
  kind?: string;
  date: string;
  taxMode: TaxMode;
  discountType: DiscountType;
  discountValue: string;
  lines: readonly DocumentGridLine[];
  taxCodes: readonly MirrorTaxCode[];
  contact?: string | null;
}

export interface DocumentCalculation {
  amounts: Record<string, DocumentLineAmounts>;
  totals: DocumentTotalsValue;
  problems: LineProblem[];
  /** True between an edit and the server's answer to it. */
  pending: boolean;
  /** Whose figures are on screen. */
  source: "mirror" | "server";
}

function request(input: DocumentCalculationInput): CalculateRequest {
  return {
    kind: input.kind,
    date: input.date,
    tax_mode: input.taxMode,
    discount_type: input.discountType,
    discount_value: input.discountType === "none" ? "0" : input.discountValue || "0",
    contact: input.contact ?? null,
    lines: input.lines.map((line) => {
      const discount = parseLineDiscount(line.discount) ?? { type: "none" as const, value: "0" };
      return {
        account: line.account,
        quantity: line.quantity || "0",
        unit_price: line.unitPrice ?? "0",
        discount_type: discount.type,
        discount_value: discount.value,
        tax_code: line.taxCode,
        description: line.description,
      };
    }),
  };
}

function mirror(input: DocumentCalculationInput, names: Map<string, string>): DocumentCalculation {
  const codes = new Map(input.taxCodes.map((code) => [code.id, code]));
  const body = request(input);
  let result: DocResult;
  try {
    result = calculateDocument({
      tax_mode: input.taxMode,
      side: input.side === "purchases" ? "purchase" : "sales",
      discount_type: body.discount_type,
      discount_value: body.discount_value,
      lines: body.lines.map((line) => ({
        quantity: line.quantity,
        unit_price: line.unit_price,
        discount_type: line.discount_type,
        discount_value: line.discount_value,
        components: line.tax_code ? (codes.get(line.tax_code)?.components ?? []) : [],
      })),
    });
  } catch {
    result = calculateDocument({ lines: [] });
  }
  const amounts: Record<string, DocumentLineAmounts> = {};
  input.lines.forEach((line, i) => {
    const figures = result.lines[i];
    if (!figures) return;
    const cents = Object.values(figures.taxes).reduce(
      (sum, amount) => sum + Math.round(Number(amount) * 100),
      0,
    );
    amounts[line.id] = { tax: (cents / 100).toFixed(2), amount: figures.net };
  });
  return {
    amounts,
    totals: {
      subtotal: result.subtotal,
      discountTotal: result.discount_total,
      taxes: Object.entries(result.tax_by_component).map(([key, amount]) => ({
        key,
        name: names.get(key) ?? key,
        amount,
      })),
      taxTotal: result.tax_total,
      total: result.total,
      taxIncluded: input.taxMode === "inclusive",
    },
    problems: [],
    pending: true,
    source: "mirror",
  };
}

function fromServer(
  input: DocumentCalculationInput,
  response: CalculateResponse,
): DocumentCalculation {
  const amounts: Record<string, DocumentLineAmounts> = {};
  input.lines.forEach((line, i) => {
    const figures = response.lines[i];
    if (figures) amounts[line.id] = { tax: figures.tax, amount: figures.net };
  });
  return {
    amounts,
    totals: {
      subtotal: response.subtotal,
      discountTotal: response.discount_total,
      taxes: response.tax_by_component,
      taxTotal: response.tax_total,
      total: response.total,
      taxIncluded: response.tax_included,
    },
    problems: response.problems,
    pending: false,
    source: "server",
  };
}

export function useDocumentCalculation(input: DocumentCalculationInput): DocumentCalculation {
  const names = useMemo(() => {
    const map = new Map<string, string>();
    for (const code of input.taxCodes) {
      for (const component of code.components) map.set(component.key, component.name);
    }
    return map;
  }, [input.taxCodes]);
  const key = JSON.stringify([request(input), input.side, input.org]);
  // `key` covers every input the figures depend on; the ref gives the effect the same input.
  const current = useRef(input);
  current.current = input;
  const local = mirror(input, names); // cheap (integer cents), so on every render
  const [server, setServer] = useState<{ key: string; value: DocumentCalculation } | null>(null);
  const latest = useRef(key);
  latest.current = key;

  useEffect(() => {
    const timer = setTimeout(() => {
      const sent = key;
      const asked = current.current;
      void documentsApi.calculate(asked.org, asked.side, request(asked)).then((result) => {
        if (result.status === 200 && latest.current === sent) {
          setServer({ key: sent, value: fromServer(asked, result.body) });
        }
      });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [key]);

  return server && server.key === key ? server.value : local;
}
