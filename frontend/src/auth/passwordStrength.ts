/**
 * Password strength for the meter on the sign-up and reset screens (A-02-T10, T11).
 *
 * Guidance only — the server decides (≥ 12 characters, not common, not like the name/email,
 * not in a known breach: A-02-T02). The meter rewards length first, because long passphrases
 * beat short complex passwords, and never reports "strong" below the 12-character minimum.
 */
export type Strength = "empty" | "tooShort" | "fair" | "good" | "strong";

export const MIN_PASSWORD_LENGTH = 12;

export function passwordStrength(password: string): Strength {
  if (!password) return "empty";
  const length = [...password].length;
  if (length < MIN_PASSWORD_LENGTH) return "tooShort";
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((re) => re.test(password)).length;
  const repeated = /^(.)\1+$/.test(password) || /^(?:0123|1234|abcd|qwer|pass)/i.test(password);
  if (repeated) return "fair";
  if (length >= 20 || (length >= 16 && classes >= 2) || classes >= 4) return "strong";
  if (length >= 14 || classes >= 3) return "good";
  return "fair";
}

/** 0–4 for the meter's filled segments. */
export function strengthScore(strength: Strength): number {
  return { empty: 0, tooShort: 1, fair: 2, good: 3, strong: 4 }[strength];
}
