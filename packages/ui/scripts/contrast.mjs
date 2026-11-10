/**
 * WCAG 2.1 contrast helpers (A-10-T04). Pure functions, shared by the CLI and the tests.
 * Formula: https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
 */
import { resolveAlias } from "./tokens-lib.mjs";

const HEX = /^#([0-9a-f]{6})([0-9a-f]{2})?$/i;

/** Relative luminance of an opaque `#rrggbb` colour. */
export function luminance(hex) {
  const match = HEX.exec(hex);
  if (!match) throw new Error(`not a #rrggbb colour: ${hex}`);
  if (match[2] && match[2].toLowerCase() !== "ff") {
    throw new Error(`translucent colour ${hex} cannot be contrast-checked; use an opaque token`);
  }
  const channels = [0, 2, 4].map((i) => parseInt(match[1].slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Contrast ratio between two colours, 1–21 (order does not matter). */
export function contrastRatio(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

/**
 * Check every pair of contrast-pairs.json against the tokens.
 * Returns one result per pair: { foreground, background, fg, bg, ratio, min, pass, use }.
 * Throws when a pair names an unknown or non-colour token.
 */
export function evaluatePairs(tokens, pairsDoc) {
  const min = pairsDoc.minRatio ?? 4.5;
  const colour = (path) => {
    const token = tokens.find((t) => t.path.join(".") === path);
    if (!token) throw new Error(`contrast pair names unknown token "${path}"`);
    if (token.type !== "color") throw new Error(`contrast pair token "${path}" is not a colour`);
    return String(resolveAlias(tokens, token.value));
  };
  return pairsDoc.pairs.map(({ foreground, background, use }) => {
    const fg = colour(foreground);
    const bg = colour(background);
    const ratio = contrastRatio(fg, bg);
    return { foreground, background, fg, bg, ratio, min, pass: ratio >= min, use };
  });
}
