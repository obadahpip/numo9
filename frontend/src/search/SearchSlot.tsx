"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { CommandPalette, isPaletteShortcut } from "./CommandPalette";
import { CreateMenu } from "./CreateMenu";
import { m } from "./messages";
import { quickCreateUrl } from "./quickCreate";
import { anotherDialogOpen, isTypingTarget, shortcutFor } from "./shortcuts";
import { ShortcutSheet } from "./ShortcutSheet";

/**
 * Top bar search slot inside an organisation (A-09-T07/T08): the "Search or jump to… Ctrl+K"
 * button and the command palette, plus the organisation's keyboard shortcuts — Ctrl/⌘+K toggles
 * the palette (unless another dialog is open), `?` opens the shortcut sheet, `N` then a letter
 * opens a quick-create action (`shortcuts.ts`); the "+" menu lists the same actions with their
 * shortcuts (F-01-T13).
 */
export function SearchSlot({ org }: { org: string }) {
  const t = useFormatMessage();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [sheet, setSheet] = useState(false);
  const pending = useRef<number | null>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isPaletteShortcut(event)) {
        if (!open && anotherDialogOpen()) return;
        event.preventDefault();
        setOpen(!open);
        return;
      }
      if (event.defaultPrevented || isTypingTarget(event.target) || anotherDialogOpen()) return;
      const action = shortcutFor(event, pending.current, Date.now());
      pending.current = action.kind === "pending" ? Date.now() : null;
      if (action.kind === "sheet") {
        event.preventDefault();
        setSheet(true);
      } else if (action.kind === "create") {
        event.preventDefault();
        router.push(quickCreateUrl(org, action.entry));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, org, router]);

  return (
    <div className="flex items-center gap-2">
      <CommandPalette
        org={org}
        open={open}
        onOpenChange={setOpen}
        navigate={(href) => router.push(href)}
        trigger={
          <button
            type="button"
            aria-keyshortcuts="Control+K Meta+K"
            className="flex min-h-touch-target w-60 items-center rounded-md border border-border-inverse bg-surface-inverse-hover px-3 text-start text-sm text-fg-inverse-muted"
          >
            {t(m.button)}
            <kbd className="ms-auto font-sans text-xs">{t(m.keys)}</kbd>
          </button>
        }
      />
      <CreateMenu org={org} />
      <ShortcutSheet open={sheet} onOpenChange={setSheet} />
    </div>
  );
}
