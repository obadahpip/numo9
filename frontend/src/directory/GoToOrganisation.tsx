"use client";

import { Dialog, HighlightedText, StatusBadge } from "@numo9/ui";
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { useFormatMessage } from "@/i18n";
import { orgModuleUrl, practiceDirectoryUrl } from "@/routing/routes";

import { directoryApi, formatBn, type DirectoryRow } from "./api";
import { statusText } from "./columns";
import { SEARCH_DEBOUNCE_MS, useDebounced } from "./useDebounced";
import { m } from "./messages";

export const GOTO_RESULTS = 8;

/** Ctrl+K / ⌘+K anywhere in the app (not while another dialog is open). */
export function isGoToShortcut(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey">) {
  return (event.ctrlKey || event.metaKey) && (event.key === "k" || event.key === "K");
}

export interface GoToOrganisationProps {
  /** Practice whose directory is searched. */
  practice: string;
  navigate?: (href: string) => void;
  openTab?: (href: string) => void;
  /** Controlled open state (tests, the top bar button). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

/**
 * "Go to organisation" (V-01-T13): `Ctrl/⌘+K` anywhere opens it; it uses the directory's own
 * search (`GET /api/v1/practice/orgs`: name, BN with or without spaces, owner, tag — accents
 * ignored), 150 ms after the last key. `↑/↓` move, `Enter` opens the organisation's Home,
 * `Ctrl/⌘+Enter` opens it in a new tab, `Esc` closes and returns focus. ARIA combobox + listbox;
 * the number of results is announced. (The A-09 command palette later takes over the shortcut
 * and includes this search as its "Organisations" group.)
 */
export function GoToOrganisation({
  practice,
  navigate,
  openTab,
  open: controlledOpen,
  onOpenChange,
}: GoToOrganisationProps) {
  const t = useFormatMessage();
  const [ownOpen, setOwnOpen] = useState(false);
  const open = controlledOpen ?? ownOpen;
  const setOpen = useCallback(
    (next: boolean) => {
      if (controlledOpen === undefined) setOwnOpen(next);
      onOpenChange?.(next);
    },
    [controlledOpen, onOpenChange],
  );
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<DirectoryRow[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [active, setActive] = useState(0);
  const inputId = useId();
  const listId = useId();
  const input = useRef<HTMLInputElement>(null);
  const q = useDebounced(query, SEARCH_DEBOUNCE_MS);

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (!isGoToShortcut(event)) return;
      if (!open && document.querySelector("[role=dialog]")) return;
      event.preventDefault();
      setOpen(!open);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setRows([]);
      setState("idle");
      setActive(0);
    }
  }, [open]);

  useEffect(() => {
    if (!open || !q.trim()) {
      setRows([]);
      setState("idle");
      return;
    }
    const controller = new AbortController();
    setState("loading");
    void directoryApi
      .list({
        practice,
        q,
        pageSize: GOTO_RESULTS,
        columns: ["bn", "province", "package", "status"],
        facets: false,
        signal: controller.signal,
      })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result.status === 200 && Array.isArray(result.body.results)) {
          setRows(result.body.results);
          setActive(0);
          setState("ready");
        } else {
          setState("error");
        }
      });
    return () => controller.abort();
  }, [open, q, practice]);

  const go = (row: DirectoryRow, newTab: boolean) => {
    const href = orgModuleUrl(row.id, "home");
    setOpen(false);
    if (newTab) (openTab ?? ((h: string) => window.open(h, "_blank", "noopener")))(href);
    else (navigate ?? ((h: string) => window.location.assign(h)))(href);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!rows.length) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current + step + rows.length) % rows.length);
    } else if (event.key === "Enter" && rows[active]) {
      event.preventDefault();
      go(rows[active], event.ctrlKey || event.metaKey);
    }
  };

  const optionId = (index: number) => `${listId}-option-${index}`;
  const announcement =
    state === "ready"
      ? t(m.gotoResults, { count: rows.length })
      : state === "error"
        ? t(m.gotoFailed)
        : "";

  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      title={t(m.gotoTitle)}
      closeLabel={t(m.close)}
      size="md"
    >
      <div className="flex flex-col gap-3" data-goto="">
        <label htmlFor={inputId} className="sr-only">
          {t(m.gotoSearch)}
        </label>
        <input
          ref={input}
          id={inputId}
          role="combobox"
          aria-expanded={rows.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={rows.length ? optionId(active) : undefined}
          autoComplete="off"
          autoFocus
          placeholder={t(m.gotoSearch)}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onKeyDown}
          className="min-h-touch-target w-full rounded-md border border-border-strong bg-surface px-3 text-base text-fg outline-none focus-visible:outline-2 focus-visible:outline-border-focus"
        />
        <ul id={listId} role="listbox" aria-label={t(m.gotoTitle)} className="flex flex-col gap-1">
          {rows.map((row, index) => (
            <li
              key={row.id}
              id={optionId(index)}
              role="option"
              aria-selected={index === active}
              onMouseEnter={() => setActive(index)}
              onClick={(event) => go(row, event.ctrlKey || event.metaKey)}
              className={
                "cursor-pointer rounded-md px-3 py-2 " +
                (index === active ? "border-s-4 border-border-accent bg-surface-accent-subtle" : "")
              }
            >
              <span className="block font-semibold text-fg">
                <HighlightedText text={row.name} query={q} />
              </span>
              <span className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
                {row.bn ? (
                  <span className="tabular-nums">
                    <HighlightedText text={formatBn(row.bn)} query={q} />
                  </span>
                ) : null}
                {row.province ? <span>{row.province}</span> : null}
                {row.package_name ? <span>{row.package_name}</span> : null}
                {row.status ? <StatusBadge status={row.status} label={statusText(t, row)} /> : null}
              </span>
            </li>
          ))}
        </ul>
        {state === "idle" ? <p className="text-sm text-fg-muted">{t(m.gotoTyping)}</p> : null}
        <p role="status" className="text-sm text-fg-muted">
          {announcement}
        </p>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2 text-xs text-fg-muted">
          <span>{t(m.gotoHint)}</span>
          <a href={practiceDirectoryUrl(practice)} className="font-semibold text-fg underline">
            {t(m.gotoOpenDirectory)}
          </a>
        </div>
      </div>
    </Dialog>
  );
}
