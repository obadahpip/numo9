/**
 * Find & recode — the results grid's selection (C-07-T11): line keys `entry:line_no`, chosen
 * row by row, by page, or **all across pages** from the search's `keys` (every included line,
 * with the fingerprint the preview compares again at execute, C-07-T06).
 */
import type { LineKey } from "./api";

export const keyOf = (line: { entry: string; line_no: number }) => `${line.entry}:${line.line_no}`;

export function toggle(selected: Set<string>, key: string): Set<string> {
  const next = new Set(selected);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}

export function setMany(selected: Set<string>, keys: string[], on: boolean): Set<string> {
  const next = new Set(selected);
  for (const key of keys) {
    if (on) next.add(key);
    else next.delete(key);
  }
  return next;
}

/** The chosen lines as the API takes them, in the search's order. */
export function chosen(all: LineKey[], selected: Set<string>): LineKey[] {
  return all.filter((key) => selected.has(keyOf(key)));
}
