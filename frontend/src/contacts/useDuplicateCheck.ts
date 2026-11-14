"use client";

import { useEffect, useRef, useState } from "react";

import { findDuplicates, isCheckable, type DuplicateMatch, type DuplicateQuery } from "./api";

/** Wait after the last keystroke before asking (B-01-T16: the panel shows within 300 ms). */
export const DUPLICATE_DEBOUNCE_MS = 250;

export type DuplicateStatus = "idle" | "checking" | "ready" | "error";

export interface DuplicateCheck {
  matches: DuplicateMatch[];
  status: DuplicateStatus;
}

/**
 * Live duplicate check while a contact is typed (B-01-T16): debounced, one request in flight
 * per pause, answers that arrive late for an older text are dropped, and the last results stay
 * on screen while the next check runs (no flicker). Nothing is asked until the query is worth it
 * (`isCheckable`).
 */
export function useDuplicateCheck(
  org: string,
  query: DuplicateQuery,
  { delay = DUPLICATE_DEBOUNCE_MS, fetcher }: { delay?: number; fetcher?: typeof fetch } = {},
): DuplicateCheck {
  const [state, setState] = useState<DuplicateCheck>({ matches: [], status: "idle" });
  const latest = useRef(0);
  const { name, email, bn, taxId, exclude } = query;

  useEffect(() => {
    const current = { name, email, bn, taxId, exclude };
    const request = ++latest.current;
    if (!isCheckable(current)) {
      setState({ matches: [], status: "idle" });
      return;
    }
    setState((previous) => ({ ...previous, status: "checking" }));
    const timer = setTimeout(() => {
      void findDuplicates(org, current, fetcher).then((result) => {
        if (request !== latest.current) return; // the text changed since: a newer check wins
        if (result.status === 200 && Array.isArray(result.body.results)) {
          setState({ matches: result.body.results, status: "ready" });
        } else {
          setState({ matches: [], status: "error" });
        }
      });
    }, delay);
    return () => clearTimeout(timer);
  }, [org, name, email, bn, taxId, exclude, delay, fetcher]);

  return state;
}
