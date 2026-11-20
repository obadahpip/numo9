"use client";

import { shortcutOf } from "./quickCreate";
import { quickCreateById } from "./shortcuts";

/**
 * Inline shortcut hint on a quick-create button or link (A-09-T08): `New contact  N C`. The keys
 * are visual only (the shortcut sheet `?` lists them for assistive technology).
 */
export function ShortcutHint({ id }: { id: string }) {
  const entry = quickCreateById(id);
  if (!entry) return null;
  return (
    <kbd
      aria-hidden="true"
      data-shortcut={shortcutOf(entry)}
      className="ms-2 rounded border border-current/40 px-1 font-sans text-xs opacity-80"
    >
      {shortcutOf(entry)}
    </kbd>
  );
}
