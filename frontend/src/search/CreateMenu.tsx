"use client";

/**
 * The top bar's "+" menu (F-01-T13; A-09-T06 registry): every quick-create action the person may
 * use, each with its keyboard shortcut (`N S` — Spend money…). What the package lacks stays,
 * disabled, with the reason (U-03: never hidden). A menu button: Enter/Space/↓ open it and focus
 * the first item, ↑/↓ move (wrapping), Esc closes and returns focus to the button.
 */
import { LockIcon, PlusIcon } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { decide, useEntitlements } from "@/entitlements/store";
import { useFormatMessage } from "@/i18n";

import { myPermissions } from "./api";
import { m } from "./messages";
import { offeredQuickCreates, quickCreateUrl, shortcutOf } from "./quickCreate";

export function CreateMenu({ org }: { org: string }) {
  const fm = useFormatMessage();
  const entitlements = useEntitlements();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [permissions, setPermissions] = useState<Set<string> | null | undefined>(undefined);
  const button = useRef<HTMLButtonElement>(null);
  const items = useRef<(HTMLElement | null)[]>([]);
  const [focus, setFocus] = useState<number | null>(null);

  useEffect(() => {
    if (!open || permissions !== undefined) return;
    myPermissions(org)
      .then(setPermissions)
      .catch(() => setPermissions(null));
  }, [open, org, permissions]);

  const offered = useMemo(
    () =>
      permissions === undefined
        ? []
        : offeredQuickCreates(permissions, (feature) => {
            const decision = decide(entitlements, feature);
            return decision.state === "gated"
              ? fm(m.locked, { product: decision.productName ?? decision.product ?? "" })
              : null;
          }),
    [permissions, entitlements, fm],
  );

  useEffect(() => {
    if (open && focus !== null) items.current[focus]?.focus();
  }, [open, focus, offered.length]);

  const close = () => {
    setOpen(false);
    setFocus(null);
    button.current?.focus();
  };

  const onMenuKey = (event: KeyboardEvent) => {
    const count = offered.length;
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown" && count) {
      event.preventDefault();
      setFocus((i) => ((i ?? -1) + 1) % count);
    } else if (event.key === "ArrowUp" && count) {
      event.preventDefault();
      setFocus((i) => ((i ?? 0) - 1 + count) % count);
    } else if (event.key === "Tab") {
      setOpen(false);
    }
  };

  return (
    <div className="relative" data-create-menu="">
      <button
        ref={button}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={`${id}-menu`}
        aria-label={fm(m.createMenu)}
        onClick={() => {
          setOpen((v) => !v);
          setFocus(0);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
            setFocus(0);
          }
        }}
        className="flex min-h-touch-target min-w-touch-target items-center justify-center rounded-md border border-border-inverse bg-surface-inverse-hover px-3 text-lg font-semibold text-fg-inverse"
      >
        <PlusIcon />
      </button>
      {open ? (
        <ul
          id={`${id}-menu`}
          role="menu"
          aria-label={fm(m.createMenu)}
          onKeyDown={onMenuKey}
          className="absolute end-0 z-50 mt-2 w-72 rounded-md border border-border bg-surface p-1 text-fg shadow-lg"
        >
          {permissions === undefined ? (
            <li role="none" className="px-3 py-2 text-sm text-fg-muted">
              {fm(m.loading)}
            </li>
          ) : null}
          {offered.map(({ entry, reason }, index) => {
            const content = (
              <>
                <span className="flex min-w-0 flex-col">
                  <span className="truncate font-medium">{fm(entry.label)}</span>
                  {reason ? (
                    <span className="flex items-center gap-1 text-xs text-fg-muted">
                      <span aria-hidden="true" className="inline-flex size-3">
                        <LockIcon />
                      </span>
                      {reason}
                    </span>
                  ) : null}
                </span>
                <kbd className="ms-auto shrink-0 rounded border border-border px-1.5 font-sans text-xs text-fg-muted">
                  <span className="sr-only">{fm(m.shortcut, { keys: shortcutOf(entry) })}</span>
                  <span aria-hidden="true">{shortcutOf(entry)}</span>
                </kbd>
              </>
            );
            const className =
              "flex min-h-touch-target w-full items-center gap-3 rounded-sm px-3 text-start text-sm focus:bg-surface-muted focus:outline-none";
            return (
              <li role="none" key={entry.id}>
                {reason ? (
                  <span
                    role="menuitem"
                    aria-disabled="true"
                    tabIndex={-1}
                    ref={(el) => {
                      items.current[index] = el;
                    }}
                    className={`${className} cursor-not-allowed text-fg-muted`}
                    data-quick-create={entry.id}
                  >
                    {content}
                  </span>
                ) : (
                  <Link
                    role="menuitem"
                    tabIndex={-1}
                    href={quickCreateUrl(org, entry)}
                    ref={(el) => {
                      items.current[index] = el;
                    }}
                    onClick={() => setOpen(false)}
                    className={`${className} hover:bg-surface-muted`}
                    data-quick-create={entry.id}
                  >
                    {content}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
