"use client";

import * as Popover from "@radix-ui/react-popover";

import { Button } from "../primitives/Button";
import { Checkbox } from "../primitives/Checkbox";

export interface ChooserColumn {
  id: string;
  header: string;
  /** False for columns that must stay (the record's name, an amount). */
  hideable: boolean;
}

/** Column chooser (A-10-T10/T11): show or hide columns; shared by DataGrid and LineGrid. */
export function ColumnChooser({
  label,
  columns,
  hidden,
  onChange,
}: {
  label: string;
  columns: ChooserColumn[];
  hidden: string[];
  onChange: (hidden: string[]) => void;
}) {
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button>{label}</Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={4}
          aria-label={label}
          className="z-50 w-64 rounded-lg border border-border bg-surface p-2 text-fg shadow-elevation-3"
        >
          <fieldset>
            <legend className="sr-only">{label}</legend>
            {columns.map((column) => (
              <Checkbox
                key={column.id}
                label={column.header}
                checked={!hidden.includes(column.id)}
                disabled={!column.hideable}
                onCheckedChange={(checked) =>
                  onChange(
                    checked ? hidden.filter((id) => id !== column.id) : [...hidden, column.id],
                  )
                }
              />
            ))}
          </fieldset>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
