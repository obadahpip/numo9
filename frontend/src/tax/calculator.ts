/**
 * Client mirror of the server's TaxCalculator (G-01-T06) for instant feedback — the live example
 * of the code editor (G-01-T13) and the document grid (D-01-T10). Same rules: each component
 * rounded half up to the cent; inclusive amounts take the net whose exclusive calculation gives
 * the gross exactly, else the residual cent goes to the largest component; on purchases each
 * component's tax splits into the claimable part and the cost. The server's result always wins.
 *
 * Money is handled in integer cents (bigint) — no floating-point rounding.
 */

export interface CalcComponent {
  key: string;
  name?: string;
  /** Percent as a decimal string, e.g. "9.975". */
  rate: string;
  /** Claimable share on purchases, 0–100 (PST: 0). */
  claimablePct?: string | number;
}

export interface CalcComponentResult {
  key: string;
  rate: string;
  amount: string;
  claimable: string;
  cost: string;
}

export interface CalcResult {
  net: string;
  tax: string;
  gross: string;
  claimable: string;
  cost: string;
  components: CalcComponentResult[];
}

const RATE_SCALE = 10000n; // rates have 4 decimals

function toCents(value: string): bigint {
  const text = value.trim();
  const negative = text.startsWith("-");
  const [whole = "0", frac = ""] = text.replace(/^[-+]/, "").split(".");
  const cents = BigInt(whole || "0") * 100n + BigInt((frac + "00").slice(0, 2));
  // a third decimal rounds half up
  const extra = frac.length > 2 && Number(frac[2]) >= 5 ? 1n : 0n;
  const total = cents + extra;
  return negative ? -total : total;
}

function rateUnits(rate: string): bigint {
  const [whole = "0", frac = ""] = rate.trim().split(".");
  return BigInt(whole || "0") * RATE_SCALE + BigInt((frac + "0000").slice(0, 4));
}

/** Divide and round half up (away from zero), like Decimal ROUND_HALF_UP. */
function divRound(numerator: bigint, denominator: bigint): bigint {
  const negative = numerator < 0n !== denominator < 0n;
  const n = numerator < 0n ? -numerator : numerator;
  const d = denominator < 0n ? -denominator : denominator;
  const q = (2n * n + d) / (2n * d);
  return negative ? -q : q;
}

export function centsToString(cents: bigint): string {
  const negative = cents < 0n;
  const abs = negative ? -cents : cents;
  const text = `${abs / 100n}.${(abs % 100n).toString().padStart(2, "0")}`;
  return negative ? `-${text}` : text;
}

function exclusiveTaxes(net: bigint, rates: bigint[]): bigint[] {
  // tax = round(net × rate / 100), rate in units of 1/10000 %
  return rates.map((rate) => divRound(net * rate, 100n * RATE_SCALE));
}

/** The tax of ``amount`` under ``components`` (exclusive, or inclusive of tax). */
export function calculateTax(
  components: readonly CalcComponent[],
  amount: string,
  { inclusive = false, purchase = false }: { inclusive?: boolean; purchase?: boolean } = {},
): CalcResult {
  const total = toCents(amount);
  const rates = components.map((c) => rateUnits(c.rate));
  let net = total;
  let taxes: bigint[] = [];
  if (!components.length) {
    taxes = [];
  } else if (!inclusive) {
    taxes = exclusiveTaxes(total, rates);
  } else {
    const sum = rates.reduce((a, b) => a + b, 0n);
    const first = divRound(total * 100n * RATE_SCALE, 100n * RATE_SCALE + sum);
    const step = total >= 0n ? 1n : -1n;
    let found = false;
    for (const candidate of [first, first - step, first + step]) {
      const amounts = exclusiveTaxes(candidate, rates);
      if (candidate + amounts.reduce((a, b) => a + b, 0n) === total) {
        net = candidate;
        taxes = amounts;
        found = true;
        break;
      }
    }
    if (!found) {
      net = first;
      taxes = exclusiveTaxes(first, rates);
      const residual = total - first - taxes.reduce((a, b) => a + b, 0n);
      let largest = 0;
      rates.forEach((rate, i) => {
        if (rate > rates[largest]!) largest = i;
      });
      taxes[largest] = taxes[largest]! + residual;
    }
  }
  const results = components.map((c, i) => {
    const amountCents = taxes[i] ?? 0n;
    let claimable = 0n;
    if (purchase) {
      const pct = BigInt(Math.round(Number(c.claimablePct ?? 100) * 100)); // in 1/100 %
      claimable = divRound(amountCents * pct, 10000n);
    }
    const cost = purchase ? amountCents - claimable : 0n;
    return {
      key: c.key,
      rate: c.rate,
      amount: centsToString(amountCents),
      claimable: centsToString(claimable),
      cost: centsToString(cost),
    };
  });
  const tax = taxes.reduce((a, b) => a + b, 0n);
  const claimableSum = results.reduce((a, r) => a + toCents(r.claimable), 0n);
  const costSum = results.reduce((a, r) => a + toCents(r.cost), 0n);
  return {
    net: centsToString(net),
    tax: centsToString(tax),
    gross: centsToString(net + tax),
    claimable: centsToString(claimableSum),
    cost: centsToString(costSum),
    components: results,
  };
}
