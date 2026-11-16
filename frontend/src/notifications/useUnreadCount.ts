"use client";

/**
 * The bell's unread count (A-07-T09): loaded when mounted, every `POLL_MS`, when the tab comes
 * back into view and whenever this tab changes notifications (`NOTIFICATIONS_CHANGED_EVENT`).
 * `null` until the first answer; a failed check keeps the last count.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { NOTIFICATIONS_CHANGED_EVENT, unreadCount } from "./api";

export const POLL_MS = 30_000;

export function useUnreadCount(org: string | undefined): {
  count: number | null;
  refresh: () => Promise<void>;
  set: (count: number) => void;
} {
  const [count, setCount] = useState<number | null>(null);
  const alive = useRef(true);

  const refresh = useCallback(async () => {
    if (!org) return;
    const answer = await unreadCount(org);
    if (alive.current && answer.status === 200 && typeof answer.body.unread_count === "number") {
      setCount(answer.body.unread_count);
    }
  }, [org]);

  useEffect(() => {
    alive.current = true;
    if (!org) return undefined;
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    const onChange = () => void refresh();
    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, onChange);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      alive.current = false;
      clearInterval(timer);
      window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, onChange);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [org, refresh]);

  return { count, refresh, set: setCount };
}
