/**
 * Bulk selection in the directory (V-03-T08): the ticked rows (`ids`), or **all organisations
 * matching** the directory's current search and filters (`query`) — which the server evaluates
 * again; the browser never sends the list of matching ids.
 */
import { FILTER_KEYS, type DirectoryState } from "@/directory/api";

export type BulkSelection =
  | { mode: "ids"; ids: ReadonlySet<string> }
  | { mode: "all"; query: DirectoryQueryInput; count: number };

export interface DirectoryQueryInput {
  q: string;
  filters: DirectoryState["filters"];
  archived: boolean;
}

export const EMPTY_SELECTION: BulkSelection = { mode: "ids", ids: new Set() };

/** How many organisations the selection names. */
export function selectionSize(selection: BulkSelection): number {
  return selection.mode === "all" ? selection.count : selection.ids.size;
}

/** The API's `selection` body: `{"ids": [...]}` or `{"query": {...}}` (V-03-T07). */
export function selectionBody(
  selection: BulkSelection,
): { ids: string[] } | { query: Record<string, string | string[]> } {
  if (selection.mode === "ids") return { ids: [...selection.ids] };
  const query: Record<string, string | string[]> = {};
  if (selection.query.q.trim()) query.q = selection.query.q.trim();
  for (const key of FILTER_KEYS) {
    const values = selection.query.filters[key];
    if (values?.length) query[key] = [...values];
  }
  if (selection.query.archived) query.archived = "include";
  return { query };
}
