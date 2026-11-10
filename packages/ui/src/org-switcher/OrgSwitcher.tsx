"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import type { ShellLinkComponent } from "../shell/AppShell";
import { ChevronDownIcon, SearchIcon } from "../shell/icons";
import { recentOrganisations, searchOrganisations } from "./search";

/**
 * Organisation switcher (A-01-T14) for the shell's `orgSwitcher` slot.
 *
 * - The button is the active-organisation header: the organisation's name and, when the user acts
 *   through a practice, the practice badge ("via Profitex").
 * - The panel lists the 5 recent organisations, a search box over every organisation the user can
 *   access (accent-insensitive, results capped so 2,000 organisations never render at once) and an
 *   "Open directory" link to the practice directory.
 * - Choosing an organisation calls `onNavigate(hrefFor(org))`; the app builds `hrefFor` so the user
 *   stays on the equivalent page (Contacts → Contacts).
 *
 * Keyboard: Enter/Space/↓ open; typing filters; ↑/↓ move through the options; Enter opens the
 * highlighted organisation; Esc closes and returns focus to the button. ARIA combobox + listbox.
 * All visible text arrives through `labels` (i18n).
 */

export interface SwitcherOrg {
  id: string;
  name: string;
  /** Practice badge text, e.g. "via Profitex"; omitted when the user is a direct member. */
  badge?: string;
}

export interface OrgSwitcherLabels {
  /** Screen-reader prefix of the button (the visible name follows), e.g. "Switch organisation". */
  button: string;
  /** Accessible name of the panel and the search box. */
  panel: string;
  search: string;
  recent: string;
  results: string;
  noResults: string;
  loading: string;
  error: string;
  retry: string;
  openDirectory: string;
  /** Marks the active organisation in the list, e.g. "Current". */
  current: string;
  /** Shown when results are capped, e.g. (20, 143) → "Showing 20 of 143. Refine your search." */
  moreResults: (shown: number, total: number) => string;
}

export type OrgSwitcherStatus = "loading" | "ready" | "error";

export interface OrgSwitcherProps {
  labels: OrgSwitcherLabels;
  /** The active organisation (header text). */
  active: SwitcherOrg;
  /** Every organisation the user can access (empty while loading). */
  organisations: readonly SwitcherOrg[];
  status?: OrgSwitcherStatus;
  /** Organisation ids, most recently opened first. */
  recentIds: readonly string[];
  /** URL of the equivalent page in another organisation. */
  hrefFor: (org: SwitcherOrg) => string;
  /** Navigate to `href` (Next.js `router.push`); defaults to `window.location.assign`. */
  onNavigate?: (href: string, org: SwitcherOrg) => void;
  onRetry?: () => void;
  /** Practice directory ("Open directory"); hidden when the user has no practice. */
  directoryHref?: string;
  /** Results shown at most for a search. */
  maxResults?: number;
  linkComponent?: ShellLinkComponent;
}

const DefaultLink: ShellLinkComponent = (props) => <a {...props} />;

export function OrgSwitcher({
  labels,
  active,
  organisations,
  status = "ready",
  recentIds,
  hrefFor,
  onNavigate = (href) => window.location.assign(href),
  onRetry,
  directoryHref,
  maxResults = 20,
  linkComponent: Link = DefaultLink,
}: OrgSwitcherProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const baseId = useId();
  const panelId = `${baseId}-panel`;
  const listId = `${baseId}-list`;
  const optionId = (index: number) => `${baseId}-option-${index}`;

  const searching = query.trim().length > 0;
  const matches = useMemo(
    () => (searching ? searchOrganisations(organisations, query) : []),
    [organisations, query, searching],
  );
  const options = useMemo(
    () =>
      searching ? matches.slice(0, maxResults) : recentOrganisations(organisations, recentIds, 5),
    [searching, matches, maxResults, organisations, recentIds],
  );

  const close = useCallback((returnFocus: boolean) => {
    setOpen(false);
    setQuery("");
    setHighlight(0);
    if (returnFocus) button.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    input.current?.focus();
    const onPointer = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) close(false);
    };
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, [open, close]);

  useEffect(() => {
    // Keep the highlighted option in view while arrowing through results.
    document.getElementById(optionId(highlight))?.scrollIntoView?.({ block: "nearest" });
    // optionId is derived from baseId, which is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlight]);

  const choose = (org: SwitcherOrg) => {
    close(false);
    if (org.id !== active.id) onNavigate(hrefFor(org), org);
  };

  const onInputKey = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    const count = options.length;
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        if (count) setHighlight((index) => (index + 1) % count);
        break;
      case "ArrowUp":
        event.preventDefault();
        if (count) setHighlight((index) => (index - 1 + count) % count);
        break;
      case "Home":
        if (count) {
          event.preventDefault();
          setHighlight(0);
        }
        break;
      case "End":
        if (count) {
          event.preventDefault();
          setHighlight(count - 1);
        }
        break;
      case "Enter": {
        event.preventDefault();
        const org = options[highlight];
        if (org) choose(org);
        break;
      }
      case "Escape":
        event.preventDefault();
        close(true);
        break;
    }
  };

  const groupLabel = searching ? labels.results : labels.recent;

  return (
    <div ref={root} className="relative flex min-w-0 flex-1" data-org-switcher="">
      <button
        ref={button}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => (open ? close(false) : setOpen(true))}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            setOpen(true);
          }
        }}
        className="inline-flex min-h-touch-target min-w-0 flex-1 items-center gap-2 rounded-md px-2 text-start text-fg-inverse hover:bg-surface-inverse-hover"
      >
        <span className="sr-only">{labels.button}</span>
        <span data-org-name="" className="min-w-0 truncate text-sm font-semibold">
          {active.name}
        </span>
        {active.badge ? (
          <span
            data-practice-badge=""
            className="max-w-32 shrink-0 truncate rounded-full bg-surface-accent px-2 text-xs leading-5 font-bold text-fg-on-accent"
          >
            {active.badge}
          </span>
        ) : null}
        <span className="ms-auto shrink-0 text-fg-inverse-muted">
          <ChevronDownIcon />
        </span>
      </button>

      <div
        id={panelId}
        role="dialog"
        aria-label={labels.panel}
        hidden={!open}
        className="absolute start-0 top-full z-50 mt-1 w-80 max-w-[calc(100vw-1rem)] rounded-lg border border-border bg-surface text-fg shadow-elevation-3 [&_:focus-visible]:outline-border-focus"
      >
        <div className="border-b border-border p-2">
          <label className="relative block">
            <span className="sr-only">{labels.search}</span>
            <span className="pointer-events-none absolute inset-y-0 start-2 flex items-center text-fg-muted">
              <SearchIcon />
            </span>
            <input
              ref={input}
              type="search"
              role="combobox"
              autoComplete="off"
              spellCheck={false}
              aria-autocomplete="list"
              aria-expanded={open && options.length > 0}
              aria-controls={listId}
              aria-activedescendant={options.length ? optionId(highlight) : undefined}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setHighlight(0);
              }}
              onKeyDown={onInputKey}
              className="min-h-touch-target w-full rounded-md border border-border-strong bg-surface ps-9 pe-2 text-sm text-fg"
            />
          </label>
        </div>

        <div className="max-h-80 overflow-y-auto py-1">
          {status === "loading" ? (
            <p role="status" className="px-4 py-3 text-sm text-fg-muted">
              {labels.loading}
            </p>
          ) : status === "error" ? (
            <div role="alert" className="flex items-center gap-2 px-4 py-3 text-sm">
              <span className="text-fg-danger">{labels.error}</span>
              {onRetry ? (
                <button
                  type="button"
                  onClick={onRetry}
                  className="ms-auto min-h-touch-target rounded-md px-2 font-semibold text-fg-link underline"
                >
                  {labels.retry}
                </button>
              ) : null}
            </div>
          ) : (
            <>
              <p
                id={`${listId}-label`}
                className="px-4 pt-2 pb-1 text-xs font-bold tracking-wide text-fg-muted uppercase"
              >
                {groupLabel}
              </p>
              <ul id={listId} role="listbox" aria-labelledby={`${listId}-label`}>
                {options.map((org, index) => {
                  const isActive = org.id === active.id;
                  return (
                    <li
                      key={org.id}
                      id={optionId(index)}
                      role="option"
                      aria-selected={index === highlight}
                      aria-current={isActive ? "true" : undefined}
                      onMouseEnter={() => setHighlight(index)}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => choose(org)}
                      className={
                        "flex min-h-touch-target cursor-pointer items-center gap-2 px-4 text-sm " +
                        (index === highlight ? "bg-surface-muted" : "")
                      }
                    >
                      <span className={`min-w-0 truncate ${isActive ? "font-semibold" : ""}`}>
                        {org.name}
                      </span>
                      {org.badge ? (
                        <span className="shrink-0 rounded-full bg-surface-accent-subtle px-2 text-xs leading-5 text-fg-accent-strong">
                          {org.badge}
                        </span>
                      ) : null}
                      {isActive ? (
                        <span className="ms-auto shrink-0 text-xs text-fg-muted">
                          {labels.current}
                        </span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
              {searching && options.length === 0 ? (
                <p role="status" className="px-4 py-3 text-sm text-fg-muted">
                  {labels.noResults}
                </p>
              ) : null}
              {searching && matches.length > options.length ? (
                <p role="status" className="px-4 py-2 text-xs text-fg-muted">
                  {labels.moreResults(options.length, matches.length)}
                </p>
              ) : null}
            </>
          )}
        </div>

        {directoryHref ? (
          <div className="border-t border-border p-1">
            <Link
              href={directoryHref}
              onClick={() => close(false)}
              className="flex min-h-touch-target items-center rounded-md px-3 text-sm font-semibold text-fg-link hover:bg-surface-muted"
            >
              {labels.openDirectory}
            </Link>
          </div>
        ) : null}
      </div>
    </div>
  );
}
