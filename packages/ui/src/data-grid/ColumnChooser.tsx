"use client";

import * as Popover from "@radix-ui/react-popover";
import { useState, type DragEvent, type KeyboardEvent } from "react";

import { Button } from "../primitives/Button";
import { Checkbox } from "../primitives/Checkbox";
import { cn } from "../primitives/cn";

export interface ChooserColumn {
  id: string;
  header: string;
  /** False for columns that must stay (the record's name, an amount). */
  hideable: boolean;
}

export interface ColumnChooserProps {
  label: string;
  columns: ChooserColumn[];
  hidden: string[];
  onChange: (hidden: string[]) => void;
  /** Column ids in display order; with `onOrderChange` the columns can be reordered (V-01). */
  order?: string[];
  onOrderChange?: (order: string[]) => void;
  /** Shown under the list when reordering is on, e.g. "Drag to reorder, or Alt+↑/↓". */
  reorderHint?: string;
  /** Announced after a move, e.g. ("BN", 2, 9) → "BN moved to position 2 of 9". */
  movedLabel?: (column: string, position: number, total: number) => string;
}

/** `columns` in `order` (unknown ids dropped, columns missing from it appended). */
export function orderColumns<T extends { id: string }>(columns: T[], order?: string[]): T[] {
  if (!order?.length) return columns;
  const byId = new Map(columns.map((column) => [column.id, column]));
  const ordered = order.flatMap((id) => (byId.has(id) ? [byId.get(id)!] : []));
  return [...ordered, ...columns.filter((column) => !order.includes(column.id))];
}

function move(order: string[], id: string, to: number): string[] {
  const without = order.filter((item) => item !== id);
  const index = Math.max(0, Math.min(to, without.length));
  return [...without.slice(0, index), id, ...without.slice(index)];
}

/**
 * Column chooser (A-10-T10/T11; reorder V-01-T12): show or hide columns; shared by DataGrid and
 * LineGrid. With `onOrderChange`, each column can also be moved — drag its handle, or press
 * `Alt+↑` / `Alt+↓` on its checkbox — and the move is announced to screen readers.
 */
export function ColumnChooser({
  label,
  columns,
  hidden,
  onChange,
  order,
  onOrderChange,
  reorderHint,
  movedLabel,
}: ColumnChooserProps) {
  const reorderable = Boolean(onOrderChange);
  const shown = orderColumns(columns, order);
  const ids = shown.map((column) => column.id);
  const [dragging, setDragging] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const moveTo = (id: string, to: number) => {
    if (!onOrderChange) return;
    const next = move(ids, id, to);
    onOrderChange(next);
    const column = shown.find((c) => c.id === id);
    if (column && movedLabel) {
      setAnnouncement(movedLabel(column.header, next.indexOf(id) + 1, next.length));
    }
  };

  const onKey = (event: KeyboardEvent, id: string) => {
    if (!reorderable || !event.altKey) return;
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    const index = ids.indexOf(id);
    moveTo(id, event.key === "ArrowUp" ? index - 1 : index + 1);
    // keep focus on the moved column's checkbox after the re-render
    requestAnimationFrame(() =>
      document.querySelector<HTMLElement>(`[data-chooser-column="${id}"] button`)?.focus(),
    );
  };

  const onDrop = (event: DragEvent, id: string) => {
    event.preventDefault();
    if (dragging && dragging !== id) moveTo(dragging, ids.indexOf(id));
    setDragging(null);
  };

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button>{label}</Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={4}
          collisionPadding={8}
          aria-label={label}
          // Long column lists scroll inside the popover instead of running off the screen.
          className="z-50 max-h-(--radix-popover-content-available-height) w-64 overflow-y-auto rounded-lg border border-border bg-surface p-2 text-fg shadow-elevation-3"
        >
          <fieldset>
            <legend className="sr-only">{label}</legend>
            <ul className="flex flex-col">
              {shown.map((column) => (
                <li
                  key={column.id}
                  data-chooser-column={column.id}
                  draggable={reorderable}
                  onDragStart={(event) => {
                    setDragging(column.id);
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", column.id);
                  }}
                  onDragOver={(event) => {
                    if (reorderable) event.preventDefault();
                  }}
                  onDrop={(event) => onDrop(event, column.id)}
                  onDragEnd={() => setDragging(null)}
                  onKeyDown={(event) => onKey(event, column.id)}
                  className={cn(
                    "flex items-center gap-1 rounded-sm",
                    dragging === column.id && "opacity-50",
                  )}
                >
                  {reorderable ? (
                    <span
                      aria-hidden="true"
                      className="cursor-grab px-1 text-fg-muted select-none"
                      title={reorderHint}
                    >
                      ⠿
                    </span>
                  ) : null}
                  <Checkbox
                    label={column.header}
                    checked={!hidden.includes(column.id)}
                    disabled={!column.hideable}
                    onCheckedChange={(checked) =>
                      onChange(
                        checked ? hidden.filter((id) => id !== column.id) : [...hidden, column.id],
                      )
                    }
                  />
                </li>
              ))}
            </ul>
          </fieldset>
          {reorderable && reorderHint ? (
            <p className="mt-2 px-1 text-xs text-fg-muted">{reorderHint}</p>
          ) : null}
          <p role="status" className="sr-only">
            {announcement}
          </p>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
