/**
 * "Add your first bank account" dismissals (F-01-T12): hidden for 7 days per person and
 * organisation, kept in this browser (localStorage). Storage may be unavailable (private mode,
 * blocked): the prompt then simply shows again — it never blocks anything.
 */
export const DISMISS_DAYS = 7;
const DAY_MS = 24 * 60 * 60 * 1000;

const key = (org: string) => `numo9.banking.noBankPrompt.${org}`;

function storage(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}

export function isDismissed(org: string, now: number = Date.now()): boolean {
  const raw = storage()?.getItem(key(org));
  const at = raw ? Number(raw) : NaN;
  return Number.isFinite(at) && now - at < DISMISS_DAYS * DAY_MS;
}

export function dismiss(org: string, now: number = Date.now()): void {
  try {
    storage()?.setItem(key(org), String(now));
  } catch {
    // Storage full or blocked: the prompt shows again next time.
  }
}
