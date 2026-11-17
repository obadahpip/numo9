"use client";

/**
 * The directory's selection bar content (V-03-T08), inside the grid's bulk bar: how many rows
 * are ticked, "Select all 1,240 matching" (the server's query), and the bulk actions.
 */
import { Button } from "@numo9/ui";

import { useFormatMessage } from "@/i18n";

import { m } from "./messages";
import { selectionSize, type BulkSelection } from "./selection";

export type BulkActionKey = "group" | "tags" | "staff" | "settings" | "message" | "export";
export const BULK_ACTIONS: BulkActionKey[] = [
  "group",
  "tags",
  "staff",
  "settings",
  "message",
  "export",
];

export interface SelectionBarProps {
  selection: BulkSelection;
  /** Organisations matching the directory's search and filters (the server's count). */
  matching: number;
  onSelectAll: () => void;
  onAction: (action: BulkActionKey) => void;
}

export function SelectionBar({ selection, matching, onSelectAll, onAction }: SelectionBarProps) {
  const fm = useFormatMessage();
  const size = selectionSize(selection);
  return (
    <div className="flex flex-wrap items-center gap-2" data-selection-bar="">
      {selection.mode === "all" ? (
        <span className="text-sm font-semibold" role="status">
          {fm(m.allSelected, { count: size })}
        </span>
      ) : size < matching ? (
        <button
          type="button"
          className="min-h-touch-target px-2 text-sm font-semibold text-fg-inverse-accent underline"
          onClick={onSelectAll}
        >
          {fm(m.selectAll, { count: matching })}
        </button>
      ) : null}
      <div role="group" aria-label={fm(m.actions)} className="flex flex-wrap gap-2">
        {BULK_ACTIONS.map((action) => (
          <Button key={action} size="sm" variant="secondary" onClick={() => onAction(action)}>
            {fm(m[action])}
          </Button>
        ))}
      </div>
    </div>
  );
}
