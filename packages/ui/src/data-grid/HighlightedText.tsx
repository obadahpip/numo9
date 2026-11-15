import { Fragment } from "react";

/** One character folded the way the search folds it (lower case, accents removed). */
function foldChar(char: string): string {
  return char
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase("en-CA");
}

const WORD = /[\p{L}\p{N}]/u;

/**
 * Ranges `[start, end)` of `text` that the directory search matched (V-01-T10), mirroring the
 * server: each query word at the start of a word, accents and case ignored ("erab" → "Érable");
 * a BN-like query (digits, spaces, dashes; 3+ digits) matched across spaces ("123 456" →
 * "123 456 782" or "123456782").
 */
export function highlightRanges(text: string, query: string): [number, number][] {
  const ranges: [number, number][] = [];
  if (!text || !query.trim()) return ranges;
  const folded = Array.from(text, foldChar);
  const flat = folded.join("");
  // index in `flat` → index in `text` (folding can drop combining marks but keeps one char
  // per original character here, because Array.from splits by code point)
  const starts: number[] = [];
  let position = 0;
  for (const piece of folded) {
    starts.push(position);
    position += piece.length;
  }
  const toText = (flatIndex: number) => {
    let index = starts.findIndex((start) => start >= flatIndex);
    if (index === -1) index = starts.length;
    return index;
  };

  const words = Array.from(new Set(foldQuery(query).match(/[\p{L}\p{N}]+/gu) ?? []));
  for (const word of words) {
    let from = 0;
    for (;;) {
      const at = flat.indexOf(word, from);
      if (at === -1) break;
      const before = at === 0 ? "" : flat[at - 1]!;
      if (!before || !WORD.test(before)) ranges.push([toText(at), toText(at + word.length)]);
      from = at + 1;
    }
  }

  const compact = query.replace(/[\s-]/g, "");
  if (/^\d{3,}$/.test(compact)) {
    const digitAt: number[] = [];
    Array.from(text).forEach((char, index) => {
      if (/\d/.test(char)) digitAt.push(index);
    });
    const digits = digitAt.map((index) => Array.from(text)[index]).join("");
    let from = 0;
    for (;;) {
      const at = digits.indexOf(compact, from);
      if (at === -1) break;
      ranges.push([digitAt[at]!, digitAt[at + compact.length - 1]! + 1]);
      from = at + 1;
    }
  }
  return merge(ranges);
}

function foldQuery(query: string): string {
  return Array.from(query, foldChar).join("");
}

function merge(ranges: [number, number][]): [number, number][] {
  const sorted = [...ranges].sort((a, b) => a[0] - b[0]);
  const out: [number, number][] = [];
  for (const range of sorted) {
    const last = out.at(-1);
    if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
    else out.push([range[0], range[1]]);
  }
  return out;
}

/** `text` with the parts matching `query` in `<mark>` (V-01-T10 search highlighting). */
export function HighlightedText({ text, query }: { text: string; query: string }) {
  const ranges = highlightRanges(text, query);
  if (!ranges.length) return <>{text}</>;
  const chars = Array.from(text);
  const parts: { text: string; mark: boolean }[] = [];
  let cursor = 0;
  for (const [start, end] of ranges) {
    if (start > cursor) parts.push({ text: chars.slice(cursor, start).join(""), mark: false });
    parts.push({ text: chars.slice(start, end).join(""), mark: true });
    cursor = end;
  }
  if (cursor < chars.length) parts.push({ text: chars.slice(cursor).join(""), mark: false });
  return (
    <>
      {parts.map((part, index) =>
        part.mark ? (
          <mark key={index} className="rounded-sm bg-surface-accent-subtle font-semibold text-fg">
            {part.text}
          </mark>
        ) : (
          <Fragment key={index}>{part.text}</Fragment>
        ),
      )}
    </>
  );
}
