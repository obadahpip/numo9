/**
 * Exact decimal arithmetic for amounts (A-10-T11 totals): decimal strings are scaled to BigInt,
 * so totals never pick up binary floating-point error (0.1 + 0.2 = 0.30, not 0.30000000000000004).
 */
const DECIMAL = /^-?\d+(\.\d+)?$/;

function toScaled(value: string, digits: number): bigint {
  if (!DECIMAL.test(value)) throw new RangeError(`Not a decimal amount: "${value}"`);
  const negative = value.startsWith("-");
  const [int = "0", frac = ""] = value.replace("-", "").split(".");
  if (frac.length > digits && /[1-9]/.test(frac.slice(digits))) {
    throw new RangeError(`"${value}" has more than ${digits} decimal places`);
  }
  const scaled = BigInt(int + frac.slice(0, digits).padEnd(digits, "0"));
  return negative ? -scaled : scaled;
}

function fromScaled(value: bigint, digits: number): string {
  const negative = value < 0n;
  const text = (negative ? -value : value).toString().padStart(digits + 1, "0");
  const int = text.slice(0, text.length - digits);
  const frac = text.slice(text.length - digits);
  const result = digits ? `${int}.${frac}` : int;
  return negative ? `-${result}` : result;
}

/** Sum of decimal strings (empty / null values count as zero), with `digits` places. */
export function sumDecimals(values: readonly (string | null | undefined)[], digits = 2): string {
  let total = 0n;
  for (const value of values) if (value) total += toScaled(value, digits);
  return fromScaled(total, digits);
}

/** a − b for decimal strings. */
export function subtractDecimals(a: string, b: string, digits = 2): string {
  return fromScaled(toScaled(a, digits) - toScaled(b, digits), digits);
}

/** −1, 0 or 1. */
export function compareDecimals(a: string, b: string, digits = 2): number {
  const diff = toScaled(a, digits) - toScaled(b, digits);
  return diff === 0n ? 0 : diff < 0n ? -1 : 1;
}

export function isZeroDecimal(value: string): boolean {
  return !/[1-9]/.test(value);
}

/** |value| as a decimal string. */
export function absDecimal(value: string): string {
  return value.startsWith("-") ? value.slice(1) : value;
}
