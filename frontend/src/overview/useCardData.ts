"use client";

/**
 * One overview card's data (D-09-T10): loads on mount and when `key` changes, independently of the
 * page's other cards; a failure gives the card its own error — what failed, why, **Try again**
 * and the support reference — never a silent "Unable to load".
 *
 * Every attempt sends a fresh `X-Request-ID` (`newRequestId`), so the reference exists even when
 * the request never reached the server; the API echoes it and logs it with the request.
 */
import type { OverviewCardError, OverviewCardLabels, OverviewCardState } from "@numo9/ui";
import { useCallback, useEffect, useRef, useState } from "react";

import { newRequestId, REQUEST_ID_HEADER, type ApiResult } from "@/auth/client";
import type { FormatMessage } from "@/i18n";

import { m } from "./messages";

export type CardLoader<T> = (headers: Record<string, string>) => Promise<ApiResult<T>>;

export interface CardData<T> {
  status: "loading" | "ready" | "error";
  data: T | null;
  /** HTTP status of the failed attempt (0: offline). */
  failure: { status: number; reference?: string } | null;
  retrying: boolean;
  retry: () => void;
}

export function useCardData<T>(
  load: CardLoader<T>,
  /** What the data depends on (organisation, filters …): a change loads again. */
  key: string,
  accept: (result: ApiResult<T>) => boolean = (result) => result.status === 200,
): CardData<T> {
  const [data, setData] = useState<T | null>(null);
  const [failure, setFailure] = useState<CardData<T>["failure"]>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const loader = useRef({ load, accept });
  useEffect(() => {
    loader.current = { load, accept };
  });

  useEffect(() => {
    let cancelled = false;
    const reference = newRequestId();
    const { load: run, accept: ok } = loader.current;
    void run({ [REQUEST_ID_HEADER]: reference }).then((result) => {
      if (cancelled) return;
      if (ok(result)) {
        setData(result.body);
        setFailure(null);
      } else {
        setFailure({ status: result.status, reference: result.requestId ?? reference });
      }
      setLoading(false);
      setRetrying(false);
    });
    return () => {
      cancelled = true;
    };
  }, [key, attempt]);

  const retry = useCallback(() => {
    setRetrying(true);
    setAttempt((n) => n + 1);
  }, []);

  const status = failure ? "error" : loading && data === null ? "loading" : "ready";
  return { status, data, failure, retrying, retry };
}

/** The card's labels in the active language. */
export function cardLabels(fm: FormatMessage, card: string): OverviewCardLabels {
  return {
    loading: fm(m.loading, { card }),
    retry: fm(m.retry),
    reference: (reference) => fm(m.reference, { reference }),
  };
}

/** The card's error: names the card, explains the failure, carries the reference. */
export function cardError(
  fm: FormatMessage,
  card: string,
  failure: { status: number; reference?: string },
): OverviewCardError {
  const body =
    failure.status === 0
      ? fm(m.offline)
      : failure.status >= 500
        ? fm(m.server)
        : failure.status === 403
          ? fm(m.denied)
          : fm(m.other);
  return { title: fm(m.failed, { card }), body, reference: failure.reference };
}

/**
 * The state props of an `OverviewCard` for this data: `status`, `labels`, and on failure the
 * `error` and `onRetry` — spread them on the card: `<OverviewCard {...cardState(...)} …>`.
 */
export function cardState<T>(
  fm: FormatMessage,
  title: string,
  card: CardData<T>,
): OverviewCardState & { title: string; labels: OverviewCardLabels; retrying?: boolean } {
  const labels = cardLabels(fm, title);
  if (card.status === "error" && card.failure) {
    return {
      title,
      status: "error",
      labels,
      error: cardError(fm, title, card.failure),
      onRetry: card.retry,
      retrying: card.retrying,
    };
  }
  return { title, status: card.status === "error" ? "loading" : card.status, labels };
}
