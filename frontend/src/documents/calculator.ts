/**
 * Client mirror of the server's DocumentCalculator (D-01-T10) for instant feedback in the
 * document grid. Same rules as `numo9.documents.calculator`:
 *
 * - line amount = round(quantity × unit price) to the cent (half up); line discount as an amount
 *   (at most the line) or a percent; net = amount − discount;
 * - document discount (amount, at most the lines' total, or percent) allocated pro-rata to the
 *   lines' nets, the cents left by rounding going one by one to the largest lines;
 * - tax per component per line on the taxable amount (net − share): exclusive, inclusive (backed
 *   out with the residual-cent rule) or none — via the tax calculator mirror (G-01).
 *
 * Money is integer cents (bigint). The backend tests and this mirror's Vitest suite run the same
 * fixture JSON (`backend/tests/fixtures/documents`). The server's result always wins.
 */
import { calculateTax, centsToString, type CalcComponent } from "@/tax/calculator";

export type TaxMode = "exclusive" | "inclusive" | "no_tax";
export type DiscountType = "none" | "amount" | "percent";

export interface DocLineInput {
  quantity?: string;
  unit_price?: string;
  discount_type?: DiscountType;
  discount_value?: string;
  components?: readonly { key: string; rate: string; claimable_pct?: string }[];
}

export interface DocInput {
  lines: readonly DocLineInput[];
  tax_mode?: TaxMode;
  side?: "sales" | "purchase";
  discount_type?: DiscountType;
  discount_value?: string;
}

export interface DocLineResult {
  gross: string;
  line_discount: string;
  net: string;
  discount_share: string;
  taxable: string;
  exclusive: string;
  taxes: Record<string, string>;
}

export interface DocResult {
  lines: DocLineResult[];
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total: string;
  net_total: string;
  tax_by_component: Record<string, string>;
}

export class CalculationError extends Error {}

const SCALE = 10000n; // quantities, prices, percents: 4 decimals

function units(value: string | undefined, fallback = "0"): bigint {
  const text = (value ?? fallback).trim() || fallback;
  const negative = text.startsWith("-");
  const [whole = "0", frac = ""] = text.replace(/^[-+]/, "").split(".");
  const n = BigInt(whole || "0") * SCALE + BigInt((frac + "0000").slice(0, 4));
  return negative ? -n : n;
}

function divRound(numerator: bigint, denominator: bigint): bigint {
  const negative = numerator < 0n !== denominator < 0n;
  const n = numerator < 0n ? -numerator : numerator;
  const d = denominator < 0n ? -denominator : denominator;
  const q = (2n * n + d) / (2n * d);
  return negative ? -q : q;
}

const min = (a: bigint, b: bigint): bigint => (a < b ? a : b);
/** A 4-decimal value rounded half up to cents. */
const toCents = (value: bigint): bigint => divRound(value, 100n);
const fromCents = (cents: string): bigint => units(cents) / 100n;

function lineDiscount(gross: bigint, line: DocLineInput): bigint {
  const kind = line.discount_type ?? "none";
  const value = units(line.discount_value);
  if (kind === "none" || value === 0n) return 0n;
  if (value < 0n) throw new CalculationError("A discount can't be negative.");
  if (kind === "amount") return gross >= 0n ? min(toCents(value), gross) : 0n;
  if (kind === "percent") {
    if (value > 100n * SCALE) throw new CalculationError("A percent discount is at most 100 %.");
    return divRound(gross * value, 100n * SCALE);
  }
  throw new CalculationError(`Unknown discount type ${String(kind)}.`);
}

export function documentDiscount(
  nets: readonly bigint[],
  kind: DiscountType,
  raw?: string,
): bigint {
  const value = units(raw);
  if (kind === "none" || value === 0n) return 0n;
  if (value < 0n) throw new CalculationError("A discount can't be negative.");
  const base = nets.reduce((sum, n) => (n > 0n ? sum + n : sum), 0n);
  if (kind === "amount") return min(toCents(value), base);
  if (kind === "percent") {
    if (value > 100n * SCALE) throw new CalculationError("A percent discount is at most 100 %.");
    return divRound(base * value, 100n * SCALE);
  }
  throw new CalculationError(`Unknown discount type ${String(kind)}.`);
}

/** Pro-rata shares of `discount` (cents): Σ shares = discount, 0 ≤ share ≤ net. */
export function allocate(discount: bigint, nets: readonly bigint[]): bigint[] {
  const shares = nets.map(() => 0n);
  const base = nets.reduce((sum, n) => (n > 0n ? sum + n : sum), 0n);
  if (discount === 0n || base === 0n) return shares;
  if (discount > base) throw new CalculationError("The discount is more than the lines' total.");
  nets.forEach((net, i) => {
    if (net > 0n) shares[i] = min(divRound(discount * net, base), net);
  });
  let remainder = discount - shares.reduce((a, b) => a + b, 0n);
  const order = nets
    .map((net, i) => ({ net, i }))
    .filter(({ net }) => net > 0n)
    .sort((a, b) => (a.net === b.net ? a.i - b.i : a.net > b.net ? -1 : 1))
    .map(({ i }) => i);
  const step = remainder > 0n ? 1n : -1n;
  while (remainder !== 0n) {
    let moved = false;
    for (const i of order) {
      if (remainder === 0n) break;
      const proposed = shares[i]! + step;
      if (proposed >= 0n && proposed <= nets[i]!) {
        shares[i] = proposed;
        remainder -= step;
        moved = true;
      }
    }
    if (!moved) throw new CalculationError("The discount can't be allocated.");
  }
  return shares;
}

export function calculateDocument(doc: DocInput): DocResult {
  const mode = doc.tax_mode ?? "exclusive";
  if (!["exclusive", "inclusive", "no_tax"].includes(mode)) {
    throw new CalculationError(`Unknown tax mode ${mode}.`);
  }
  const purchase = doc.side === "purchase";
  const figures = doc.lines.map((line) => {
    const gross = divRound(units(line.quantity, "1") * units(line.unit_price), 1000000n);
    const discount = lineDiscount(gross, line);
    return { line, gross, discount, net: gross - discount };
  });
  const nets = figures.map((f) => f.net);
  const discountTotal = documentDiscount(nets, doc.discount_type ?? "none", doc.discount_value);
  const shares = allocate(discountTotal, nets);
  const byComponent = new Map<string, bigint>();
  const lines: DocLineResult[] = figures.map((f, i) => {
    const share = shares[i]!;
    const taxable = f.net - share;
    const components: CalcComponent[] =
      mode === "no_tax"
        ? []
        : (f.line.components ?? []).map((c) => ({
            key: c.key,
            rate: c.rate,
            claimablePct: c.claimable_pct ?? "100",
          }));
    const tax = calculateTax(components, centsToString(taxable), {
      inclusive: mode === "inclusive",
      purchase,
    });
    const taxes: Record<string, string> = {};
    for (const part of tax.components) {
      taxes[part.key] = part.amount;
      byComponent.set(part.key, (byComponent.get(part.key) ?? 0n) + fromCents(part.amount));
    }
    return {
      gross: centsToString(f.gross),
      line_discount: centsToString(f.discount),
      net: centsToString(f.net),
      discount_share: centsToString(share),
      taxable: centsToString(taxable),
      exclusive: tax.net,
      taxes,
    };
  });
  const subtotal = nets.reduce((a, b) => a + b, 0n);
  const taxTotal = [...byComponent.values()].reduce((a, b) => a + b, 0n);
  const after = subtotal - discountTotal;
  const total = mode === "inclusive" ? after : after + taxTotal;
  const sortedKeys = [...byComponent.keys()].sort();
  return {
    lines,
    subtotal: centsToString(subtotal),
    discount_total: centsToString(discountTotal),
    tax_total: centsToString(taxTotal),
    total: centsToString(total),
    net_total: centsToString(total - taxTotal),
    tax_by_component: Object.fromEntries(
      sortedKeys.map((key) => [key, centsToString(byComponent.get(key)!)]),
    ),
  };
}
