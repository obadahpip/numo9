"use client";

/**
 * Command palette (A-09-T07): Ctrl/⌘+K in an organisation. One box finds records (contacts,
 * accounts, journals, documents, users — the search API, T05), settings pages, reports and
 * places to go, and offers the quick-create actions (T06). Groups: Recent (before anything is
 * typed), Create, Records, Settings, Reports, Go to.
 *
 * - **Gated items explained:** what the user may not do never appears (the API and the
 *   quick-create registry filter by permission); what the package lacks stays, with a lock and the
 *   reason in words (U-03 rule: never hidden). Opening it shows the module's locked panel.
 * - **Keyboard only:** focus starts in the box; ↑/↓ move (wrapping), Enter opens, Esc closes and
 *   focus returns to the button that opened it (cmdk inside the design-system dialog).
 * - Recent: the last 5 picks in this organisation, kept in this browser (`recents.ts`).
 */
import { Dialog, LockIcon } from "@numo9/ui";
import { Command } from "cmdk";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useDebounced } from "@/directory/useDebounced";
import { decide, useEntitlements } from "@/entitlements/store";
import { useFormatMessage, type FormatMessage } from "@/i18n";

import {
  EMPTY_RESULTS,
  isSearchResults,
  myPermissions,
  searchOrg,
  type SearchResults,
} from "./api";
import { m } from "./messages";
import { offeredQuickCreates, quickCreateUrl, shortcutOf, type QuickCreate } from "./quickCreate";
import { readRecents, rememberPick, type RecentPick } from "./recents";

export const PALETTE_DEBOUNCE_MS = 150;

/** Ctrl+K or ⌘+K, nothing else. */
export function isPaletteShortcut(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey">) {
  return event.key.toLowerCase() === "k" && (event.ctrlKey || event.metaKey);
}

export interface PaletteItem {
  id: string;
  title: string;
  subtitle?: string;
  url: string;
  locked?: string | null;
  shortcut?: string;
}

export interface CommandPaletteProps {
  org: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The button that opens it; focus returns there on close. */
  trigger?: ReactNode;
  navigate: (href: string) => void;
  /** Tests inject a fetch. */
  fetcher?: typeof fetch;
}

type Status = "idle" | "loading" | "ready" | "error";

export function CommandPalette({
  org,
  open,
  onOpenChange,
  trigger,
  navigate,
  fetcher,
}: Readonly<CommandPaletteProps>) {
  const fm = useFormatMessage();
  const entitlements = useEntitlements();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults>(EMPTY_RESULTS);
  const [status, setStatus] = useState<Status>("idle");
  const [attempt, setAttempt] = useState(0);
  const [permissions, setPermissions] = useState<Set<string> | null | undefined>(undefined);
  const [recents, setRecents] = useState<RecentPick[]>([]);
  const q = useDebounced(query.trim(), PALETTE_DEBOUNCE_MS);
  const latest = useRef(0);

  useEffect(() => {
    if (!open) return;
    setRecents(readRecents(org));
    if (permissions === undefined) {
      myPermissions(org)
        .then(setPermissions)
        .catch(() => setPermissions(null));
    }
  }, [open, org, permissions]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setResults(EMPTY_RESULTS);
      setStatus("idle");
    }
  }, [open]);

  useEffect(() => {
    if (!open || !q) {
      setStatus("idle");
      setResults(EMPTY_RESULTS);
      return;
    }
    const call = ++latest.current;
    setStatus("loading");
    searchOrg(org, q, fetcher)
      .then((result) => {
        if (call !== latest.current) return; // a newer query answered already
        if (result.status === 200 && isSearchResults(result.body)) {
          setResults(result.body);
          setStatus("ready");
        } else {
          setStatus("error");
        }
      })
      .catch(() => {
        if (call === latest.current) setStatus("error");
      });
  }, [open, q, org, fetcher, attempt]);

  const creates = useMemo(
    () =>
      permissions === undefined
        ? []
        : offeredQuickCreates(permissions, (feature) =>
            lockReason(fm, decide(entitlements, feature)),
          ),
    [permissions, entitlements, fm],
  );

  const createItems: PaletteItem[] = creates
    .map(({ entry, reason }) => createItem(fm, org, entry, reason))
    .filter((item) => !q || matches(item.title, q));

  const choose = useCallback(
    (item: PaletteItem) => {
      setRecents(rememberPick(org, { id: item.id, title: item.title, url: item.url }));
      onOpenChange(false);
      navigate(item.url);
    },
    [org, navigate, onOpenChange],
  );

  const groups: { key: string; label: string; items: PaletteItem[] }[] = q
    ? [
        { key: "create", label: fm(m.create), items: createItems },
        {
          key: "records",
          label: fm(m.records),
          items: results.records.map((r) => ({
            id: `records:${r.type}:${r.id}`,
            title: r.code && !r.title.includes(r.code) ? `${r.code} · ${r.title}` : r.title,
            subtitle: r.subtitle,
            url: r.url,
            locked: r.locked ? r.reason : null,
          })),
        },
        ...(["settings", "reports", "navigation"] as const).map((group) => ({
          key: group,
          label: fm(m[group]),
          items: results[group].map((s) => ({
            id: `${group}:${s.key}`,
            title: s.title,
            url: s.url,
            locked: s.locked ? s.reason : null,
          })),
        })),
      ]
    : [
        { key: "recents", label: fm(m.recents), items: recents },
        { key: "create", label: fm(m.create), items: createItems },
      ];
  const shown = groups.filter((group) => group.items.length > 0);
  const nothing = shown.length === 0;
  const values = shown.flatMap((group) => group.items.map((item) => itemValue(group.key, item)));
  const first = values[0] ?? "";
  const signature = values.join("|");
  // New results: the first one is selected (Enter opens it), as before anything moved.
  const [selected, setSelected] = useState("");
  useEffect(() => setSelected(first), [signature, first]);

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      trigger={trigger}
      title={fm(m.title)}
      closeLabel={fm(m.close)}
      size="lg"
    >
      <Command
        label={fm(m.input)}
        shouldFilter={false}
        loop
        value={selected}
        onValueChange={setSelected}
        className="flex flex-col gap-2"
      >
        <Command.Input
          autoFocus
          value={query}
          onValueChange={setQuery}
          placeholder={fm(m.input)}
          className="min-h-11 w-full rounded-md border border-border bg-surface px-3 text-base text-fg focus-visible:outline-2 focus-visible:outline-focus"
        />
        <Command.List
          aria-label={fm(m.title)}
          className="max-h-[60vh] overflow-y-auto"
          aria-busy={status === "loading"}
        >
          {status === "error" ? (
            <div role="alert" className="flex items-center gap-3 p-3 text-sm text-fg">
              <span>{fm(m.error)}</span>
              <button
                type="button"
                className="min-h-10 rounded-md border border-border px-3"
                onClick={() => setAttempt((n) => n + 1)}
              >
                {fm(m.retry)}
              </button>
            </div>
          ) : null}
          {status === "loading" && nothing ? (
            <Command.Loading>
              <p className="p-3 text-sm text-fg-muted">{fm(m.searching)}</p>
            </Command.Loading>
          ) : null}
          {nothing && status !== "loading" && status !== "error" ? (
            <p className="p-3 text-sm text-fg-muted" role="status">
              {q ? fm(m.empty, { query: q }) : fm(m.start)}
            </p>
          ) : null}
          {shown.map((group) => (
            <Command.Group
              key={group.key}
              heading={group.label}
              className="py-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-fg-muted"
            >
              {group.items.map((item) => (
                <PaletteRow
                  key={`${group.key}-${item.id}`}
                  group={group.key}
                  item={item}
                  fm={fm}
                  onSelect={choose}
                />
              ))}
            </Command.Group>
          ))}
        </Command.List>
        <p className="text-xs text-fg-muted" aria-hidden="true">
          {fm(m.hint)}
        </p>
      </Command>
    </Dialog>
  );
}

function PaletteRow({
  group,
  item,
  fm,
  onSelect,
}: {
  group: string;
  item: PaletteItem;
  fm: FormatMessage;
  onSelect: (item: PaletteItem) => void;
}) {
  return (
    <Command.Item
      value={itemValue(group, item)}
      onSelect={() => onSelect(item)}
      className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm text-fg data-[selected=true]:bg-surface-hover"
    >
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate font-medium">{item.title}</span>
        {item.subtitle ? (
          <span className="truncate text-xs text-fg-muted">{item.subtitle}</span>
        ) : null}
        {item.locked ? (
          <span className="flex items-center gap-1 text-xs text-fg-muted">
            <span aria-hidden="true" className="inline-flex size-3">
              <LockIcon />
            </span>
            <span className="sr-only">{fm(m.lockedPrefix)}</span>
            {item.locked}
          </span>
        ) : null}
      </span>
      {item.shortcut ? (
        <kbd className="shrink-0 rounded border border-border px-1.5 font-sans text-xs text-fg-muted">
          <span className="sr-only">{fm(m.shortcut, { keys: item.shortcut })}</span>
          <span aria-hidden="true">{item.shortcut}</span>
        </kbd>
      ) : null}
    </Command.Item>
  );
}

function itemValue(group: string, item: PaletteItem): string {
  return `${group}-${item.id}`;
}

function createItem(
  fm: FormatMessage,
  org: string,
  entry: QuickCreate,
  reason: string | null,
): PaletteItem {
  return {
    id: `create:${entry.id}`,
    title: fm(entry.label),
    url: quickCreateUrl(org, entry),
    locked: reason,
    shortcut: shortcutOf(entry),
  };
}

function lockReason(fm: FormatMessage, decision: ReturnType<typeof decide>): string | null {
  return decision.state === "gated"
    ? fm(m.locked, { product: decision.productName ?? decision.product ?? "" })
    : null;
}

/** Every typed word starts a word of the label, accents and case ignored. */
export function matches(label: string, query: string): boolean {
  const fold = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const words = fold(label).split(/\s+/);
  return fold(query)
    .split(/\s+/)
    .filter(Boolean)
    .every((part) => words.some((word) => word.startsWith(part)));
}
