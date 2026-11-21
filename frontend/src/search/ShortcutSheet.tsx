"use client";

import { Dialog } from "@numo9/ui";

import { useFormatMessage } from "@/i18n";

import { m } from "./messages";
import { QUICK_CREATE, shortcutOf } from "./quickCreate";

/**
 * Keyboard shortcut sheet (A-09-T08), opened with `?`: every shortcut of the app, the quick-create
 * ones from the registry (T06) — those whose screen arrives later say so.
 */
export function ShortcutSheet({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const fm = useFormatMessage();
  const general = [
    { keys: fm(m.keys), label: fm(m.button) },
    { keys: "?", label: fm(m.sheetTitle) },
  ];
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={fm(m.sheetTitle)}
      closeLabel={fm(m.close)}
    >
      <div className="flex flex-col gap-4">
        <ShortcutTable
          caption={fm(m.sheetGeneral)}
          rows={general}
          keysHeading={fm(m.sheetKeys)}
          actionHeading={fm(m.sheetAction)}
        />
        <ShortcutTable
          caption={fm(m.sheetCreate)}
          keysHeading={fm(m.sheetKeys)}
          actionHeading={fm(m.sheetAction)}
          rows={QUICK_CREATE.map((entry) => ({
            keys: shortcutOf(entry),
            label: fm(entry.label),
            note: entry.availableIn ? fm(m.sheetLater) : undefined,
          }))}
        />
        <p className="text-xs text-fg-muted">{fm(m.sheetHelp)}</p>
      </div>
    </Dialog>
  );
}

function ShortcutTable({
  caption,
  keysHeading,
  actionHeading,
  rows,
}: {
  caption: string;
  keysHeading: string;
  actionHeading: string;
  rows: { keys: string; label: string; note?: string }[];
}) {
  return (
    <table className="w-full text-sm">
      <caption className="pb-1 text-start font-semibold text-fg">{caption}</caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">{keysHeading}</th>
          <th scope="col">{actionHeading}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.keys} className="border-t border-border">
            <td className="w-24 py-1.5">
              <kbd className="rounded border border-border px-1.5 font-sans text-xs">
                {row.keys}
              </kbd>
            </td>
            <td className="py-1.5 text-fg">
              {row.label}
              {row.note ? <span className="ms-2 text-xs text-fg-muted">{row.note}</span> : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
