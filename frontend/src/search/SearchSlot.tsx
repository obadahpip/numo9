"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { CommandPalette, isPaletteShortcut } from "./CommandPalette";
import { m } from "./messages";

/**
 * Top bar search slot inside an organisation (A-09-T07): the "Search or jump to… Ctrl+K" button
 * and the command palette. Ctrl/⌘+K opens it from anywhere in the organisation (unless another
 * dialog is open) and closes it again.
 */
export function SearchSlot({ org }: { org: string }) {
  const t = useFormatMessage();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!isPaletteShortcut(event)) return;
      if (!open && anotherDialogOpen()) return;
      event.preventDefault();
      setOpen(!open);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
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
  );
}

/** A dialog on screen (a closed panel such as the org switcher's stays in the page, hidden). */
function anotherDialogOpen(): boolean {
  return [...document.querySelectorAll<HTMLElement>("[role=dialog]")].some(
    (dialog) => !dialog.hidden && dialog.closest("[hidden]") === null,
  );
}
