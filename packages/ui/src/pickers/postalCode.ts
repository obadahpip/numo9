/**
 * Canadian postal codes (A-10-T09): `A1A 1A1`. Letters D, F, I, O, Q, U never appear; W and Z
 * never start a code.
 */
const VALID = /^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z] \d[ABCEGHJ-NPRSTV-Z]\d$/;

/** Upper-case, drop anything but letters and digits, insert the space: "m5v2t6" → "M5V 2T6". */
export function formatPostalCode(input: string): string {
  const compact = input
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "")
    .slice(0, 6);
  return compact.length > 3 ? `${compact.slice(0, 3)} ${compact.slice(3)}` : compact;
}

export function isValidPostalCode(value: string): boolean {
  return VALID.test(formatPostalCode(value));
}

/** True when the code's first letter belongs to the province (M… is Ontario). */
export function postalCodeMatchesProvince(value: string, prefixes: string): boolean {
  const first = formatPostalCode(value).charAt(0);
  return first !== "" && prefixes.includes(first);
}
