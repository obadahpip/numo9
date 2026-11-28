/**
 * Regex tester logic (F-04-T11): highlight what a rule's pattern matches in a sample text, the
 * way the server compares — case-insensitive with accents folded. JavaScript's engine stands in
 * for the server's (``regex``, Python syntax): common patterns behave the same; the server checks
 * the pattern again when the rule is saved (50 ms timeout guard).
 */
export interface HighlightPart {
  text: string;
  match: boolean;
}

export interface Highlight {
  parts: HighlightPart[];
  count: number;
  error: boolean;
}

const MAX_PATTERN = 500;

/** Accents removed, length kept (one character per character) so match offsets still apply. */
export function foldAccents(text: string): string {
  return Array.from(text)
    .map(
      (c) =>
        c
          .normalize("NFD")
          .replace(/\p{Mn}/gu, "")
          .charAt(0) || c,
    )
    .join("");
}

export function highlightMatches(pattern: string, sample: string): Highlight {
  if (!pattern) return { parts: [{ text: sample, match: false }], count: 0, error: false };
  let expression: RegExp;
  try {
    if (pattern.length > MAX_PATTERN) throw new Error("too long");
    expression = new RegExp(foldAccents(pattern), "giu");
  } catch {
    return { parts: [{ text: sample, match: false }], count: 0, error: true };
  }
  const folded = foldAccents(sample);
  const parts: HighlightPart[] = [];
  let last = 0;
  let count = 0;
  for (const found of folded.matchAll(expression)) {
    const start = found.index ?? 0;
    const end = start + found[0].length;
    if (end === start) continue;
    if (start > last) parts.push({ text: sample.slice(last, start), match: false });
    parts.push({ text: sample.slice(start, end), match: true });
    last = end;
    count += 1;
  }
  if (last < sample.length) parts.push({ text: sample.slice(last), match: false });
  return { parts, count, error: false };
}
