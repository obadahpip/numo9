/**
 * Pseudo-localisation (A-10-T13): `en-XA` = en-CA text with accented look-alike letters, about
 * 30 % longer, in brackets — "[Ŝéţţîñĝš ~~~]". Untranslated (hard-coded) text stands out, and
 * layouts are checked against long French labels (Phase 0 plan §3.6: no clipping at +30 %).
 * ICU arguments (`{name}`, plural/select blocks) are left untouched so messages still format.
 */
const ACCENTS: Record<string, string> = {
  a: "á",
  b: "ƀ",
  c: "ç",
  d: "ð",
  e: "é",
  f: "ƒ",
  g: "ĝ",
  h: "ĥ",
  i: "î",
  j: "ĵ",
  k: "ķ",
  l: "ļ",
  m: "ɱ",
  n: "ñ",
  o: "ö",
  p: "þ",
  q: "ǫ",
  r: "ŕ",
  s: "š",
  t: "ţ",
  u: "û",
  v: "ṽ",
  w: "ŵ",
  x: "ẋ",
  y: "ý",
  z: "ž",
  A: "Á",
  B: "Ɓ",
  C: "Ç",
  D: "Ð",
  E: "É",
  F: "Ƒ",
  G: "Ĝ",
  H: "Ĥ",
  I: "Î",
  J: "Ĵ",
  K: "Ķ",
  L: "Ļ",
  M: "Ṁ",
  N: "Ñ",
  O: "Ö",
  P: "Þ",
  Q: "Ǫ",
  R: "Ŕ",
  S: "Š",
  T: "Ţ",
  U: "Û",
  V: "Ṽ",
  W: "Ŵ",
  X: "Ẋ",
  Y: "Ý",
  Z: "Ž",
};

export const PSEUDO_EXPANSION = 0.3;

export function pseudoLocalise(message: string): string {
  let depth = 0;
  let out = "";
  let letters = 0;
  for (const char of message) {
    if (char === "{") depth += 1;
    if (depth === 0) {
      const accented = ACCENTS[char];
      if (accented) letters += 1;
      out += accented ?? char;
    } else {
      out += char;
    }
    if (char === "}") depth = Math.max(0, depth - 1);
  }
  const padding = "~".repeat(Math.ceil(Math.max(letters, 1) * PSEUDO_EXPANSION));
  return `[${out} ${padding}]`;
}

export interface Catalog {
  [key: string]: string | Catalog;
}

/** Pseudo-localise every message of a (nested) catalogue. */
export function pseudoCatalog(catalog: Catalog): Catalog {
  const out: Catalog = {};
  for (const [key, value] of Object.entries(catalog)) {
    out[key] = typeof value === "string" ? pseudoLocalise(value) : pseudoCatalog(value);
  }
  return out;
}
