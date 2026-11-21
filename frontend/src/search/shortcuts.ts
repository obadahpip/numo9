/**
 * Global keyboard shortcuts in an organisation (A-09-T08): `?` opens the shortcut sheet; `N` then
 * a letter opens a quick-create action (`N C` → new contact, T06 registry); Ctrl/⌘+K the palette
 * (T07). Single keys never fire while typing (inputs, text areas, selects, editable content), with
 * a modifier (other than Shift for `?`), or while a dialog is open.
 */
import { QUICK_CREATE, quickCreateFor, type QuickCreate } from "./quickCreate";

/** How long after `N` the second key counts. */
export const SEQUENCE_MS = 1500;

export type ShortcutAction =
  | { kind: "sheet" }
  | { kind: "pending" }
  | { kind: "create"; entry: QuickCreate }
  | { kind: "none" };

export interface KeyLike {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
}

/** What a key press does, given when `N` was pressed last (`pendingSince`, ms) and now. */
export function shortcutFor(
  event: KeyLike,
  pendingSince: number | null,
  now: number,
): ShortcutAction {
  if (event.ctrlKey || event.metaKey || event.altKey) return { kind: "none" };
  const pending = pendingSince !== null && now - pendingSince <= SEQUENCE_MS;
  if (pending) {
    const entry = event.key.length === 1 ? quickCreateFor(event.key) : undefined;
    if (entry && !entry.availableIn) return { kind: "create", entry };
    return { kind: "none" };
  }
  if (event.key === "?") return { kind: "sheet" };
  if (event.key === "n" || event.key === "N") return { kind: "pending" };
  return { kind: "none" };
}

/** The focus is somewhere the user types. */
export function isTypingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element || typeof element.tagName !== "string") return false;
  const tag = element.tagName.toLowerCase();
  return (
    tag === "input" || tag === "textarea" || tag === "select" || element.isContentEditable === true
  );
}

/** A dialog on screen (a closed panel such as the org switcher's stays in the page, hidden). */
export function anotherDialogOpen(): boolean {
  return [...document.querySelectorAll<HTMLElement>("[role=dialog]")].some(
    (dialog) => !dialog.hidden && dialog.closest("[hidden]") === null,
  );
}

export function quickCreateById(id: string): QuickCreate | undefined {
  return QUICK_CREATE.find((entry) => entry.id === id);
}
