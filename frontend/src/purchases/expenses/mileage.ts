/**
 * Mileage calculator (E-04-T10) — the same arithmetic as the server's
 * (numo9/purchases/mileage.py `split_km` / `mileage_amount`), so the amount the form shows live is
 * the amount the claim gets: the kilometres up to the CRA threshold (5,000 business km in the
 * calendar year) at the first-tier rate, the rest at the second; the total rounded to the cent
 * (half to even, like Python's `Decimal.quantize`). Exact integer arithmetic: tenths of a
 * kilometre × ten-thousandths of a dollar.
 */
import type { FormLine } from "./fields";

export interface Rate {
  first_tier_rate: string;
  second_tier_rate: string;
  tier_threshold_km: number;
}

export interface Tier {
  tier: "first" | "after";
  km: string;
  rate: string;
  amount: string;
}

/** "12.34" → 1234 in units of 10^-places (no float rounding); NaN for anything else. */
export function scaled(text: string, places: number): number {
  const match = /^\s*(\d*)(?:\.(\d*))?\s*$/.exec(text);
  if (!match || (!match[1] && !match[2])) return Number.NaN;
  const whole = match[1] || "0";
  const fraction = (match[2] ?? "").slice(0, places).padEnd(places, "0");
  return Number(whole) * 10 ** places + Number(fraction || "0");
}

/** Round an integer number of 10^-5 dollars to cents, half to even. */
function toCents(units: number): number {
  const cents = Math.floor(units / 1000);
  const rest = units - cents * 1000;
  if (rest > 500 || (rest === 500 && cents % 2 === 1)) return cents + 1;
  return cents;
}

const money = (cents: number) => (cents / 100).toFixed(2);
const km = (tenths: number) => (tenths / 10).toFixed(1);
const rateText = (text: string) => String(Number(text));

/** Split `distance` (tenths of km) driven after `prior` (tenths) at `threshold` (tenths). */
export function splitKm(prior: number, distance: number, threshold: number): [number, number] {
  const first = Math.max(0, Math.min(distance, threshold - prior));
  return [first, distance - first];
}

/** The amount of a trip and its tiers; null when the kilometres aren't a number above 0. */
export function mileageAmount(
  distanceKm: string,
  rate: Rate,
  priorKm = "0",
): { amount: string; tiers: Tier[] } | null {
  const distance = scaled(distanceKm, 1);
  const prior = scaled(priorKm || "0", 1);
  if (!Number.isFinite(distance) || distance <= 0 || !Number.isFinite(prior)) return null;
  const [first, after] = splitKm(prior, distance, rate.tier_threshold_km * 10);
  let units = 0;
  const tiers: Tier[] = [];
  for (const [tier, part, perKm] of [
    ["first", first, rate.first_tier_rate],
    ["after", after, rate.second_tier_rate],
  ] as const) {
    if (part <= 0) continue;
    const amount = part * scaled(perKm, 4); // 10^-1 km × 10^-4 $ = 10^-5 $
    units += amount;
    tiers.push({ tier, km: km(part), rate: rateText(perKm), amount: money(toCents(amount)) });
  }
  return { amount: money(toCents(units)), tiers };
}

/**
 * Business km claimed before `line` this calendar year: `yearToDate` (the server's figure for
 * the person's other claims before the line's date) plus the earlier trips of this form — in
 * date order, then position, as the server prices them.
 */
export function priorKm(line: FormLine, lines: FormLine[], yearToDate: string): string {
  const year = line.date.slice(0, 4);
  const index = lines.indexOf(line);
  let tenths = scaled(yearToDate || "0", 1) || 0;
  lines.forEach((other, position) => {
    if (other === line || other.kind !== "mileage" || other.date.slice(0, 4) !== year) return;
    const earlier = other.date < line.date || (other.date === line.date && position < index);
    const distance = scaled(other.km, 1);
    if (earlier && Number.isFinite(distance)) tenths += distance;
  });
  return km(tenths);
}
