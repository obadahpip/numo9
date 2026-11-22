"use client";

/**
 * No-bank-account prompt (F-01-T12, wireframe 42): "Add your first bank account" on the home
 * dashboard and on Banking while the organisation has no bank account (archived ones count: the
 * organisation has set banking up). Informative only — nothing is blocked; "Hide for 7 days"
 * hides it for this person in this browser, and it comes back after 7 days if there is still no
 * account.
 */
import { Button } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { bankingApi } from "./api";
import { dismiss, isDismissed } from "./dismissal";
import { prompt } from "./messages";

export interface NoBankPromptProps {
  org: string;
  /** Known account count (the banking page has it); fetched when absent. */
  count?: number;
  /** Opens the add-account sheet; without it the button links to Banking. */
  onAdd?: () => void;
}

export function NoBankPrompt({ org, count, onAdd }: NoBankPromptProps) {
  const fm = useFormatMessage();
  const [known, setKnown] = useState<number | undefined>(count);
  const [hidden, setHidden] = useState(true);

  useEffect(() => setHidden(isDismissed(org)), [org]);
  useEffect(() => {
    if (count !== undefined) {
      setKnown(count);
      return;
    }
    let cancelled = false;
    void bankingApi.accounts(org, "all").then((result) => {
      if (!cancelled && result.status === 200 && Array.isArray(result.body?.results)) {
        setKnown(result.body.results.length);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [org, count]);

  if (hidden || known !== 0) return null;
  return (
    <section
      aria-labelledby="no-bank-prompt"
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface-info-subtle p-4"
      data-no-bank-prompt=""
    >
      <div className="flex max-w-3xl flex-col gap-1">
        <h2 id="no-bank-prompt" className="text-base font-semibold text-fg">
          {fm(prompt.title)}
        </h2>
        <p className="text-sm text-fg-muted">{fm(prompt.body)}</p>
      </div>
      <div className="flex items-center gap-2">
        {onAdd ? (
          <Button variant="primary" onClick={onAdd}>
            {fm(prompt.add)}
          </Button>
        ) : (
          <Link
            href={`/o/${org}/banking?add=1`}
            className="rounded-md bg-surface-accent px-4 py-2 text-sm font-semibold text-fg"
          >
            {fm(prompt.add)}
          </Link>
        )}
        <Button
          variant="ghost"
          onClick={() => {
            dismiss(org);
            setHidden(true);
          }}
        >
          {fm(prompt.dismiss)}
        </Button>
      </div>
    </section>
  );
}
