"use client";

/**
 * Assurance nav badge (K-09-T24): the number of **open critical + warning** findings (info and
 * acknowledged ones don't count — the summary's `attention`), shown on the Accounting item of
 * the primary navigation. The shell reads the summary once per page when the organisation has
 * `accounting.assurance.read`; the Assurance page announces every summary it loads
 * (`ASSURANCE_SUMMARY_EVENT`) so the badge follows acknowledgements and runs at once. No access
 * (403/404) or a failed request = no badge.
 */
import { useEffect, useState } from "react";

import { assuranceApi, type Summary } from "./api";

export const ASSURANCE_SUMMARY_EVENT = "numo9:assurance-summary";

/** Open critical + open warning findings. */
export function attentionCount(summary: Pick<Summary, "open">): number {
  return (summary.open.critical ?? 0) + (summary.open.warning ?? 0);
}

/** Tell the shell's badge about a freshly loaded summary. */
export function announceSummary(org: string, summary: Summary): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(ASSURANCE_SUMMARY_EVENT, { detail: { org, summary } }));
}

/** The attention count of the organisation, or `null` while unknown / not available. */
export function useAssuranceAttention(org: string | undefined, enabled: boolean): number | null {
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    if (!org || !enabled) {
      setCount(null);
      return;
    }
    let cancelled = false;
    void assuranceApi
      .summary(org)
      .then((answer) => {
        if (!cancelled && answer.status === 200 && answer.body?.open) {
          setCount(attentionCount(answer.body));
        }
      })
      .catch(() => undefined);
    const listen = (event: Event) => {
      const detail = (event as CustomEvent<{ org: string; summary: Summary }>).detail;
      if (detail?.org === org && detail.summary?.open) setCount(attentionCount(detail.summary));
    };
    window.addEventListener(ASSURANCE_SUMMARY_EVENT, listen);
    return () => {
      cancelled = true;
      window.removeEventListener(ASSURANCE_SUMMARY_EVENT, listen);
    };
  }, [org, enabled]);

  return count;
}
