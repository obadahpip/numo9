"use client";

import { Badge, Button } from "@numo9/ui";
import Link from "next/link";
import { useId, useState } from "react";

import { useFormatMessage, type FormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import type { DuplicateMatch, DuplicateQuery, DuplicateReason } from "./api";
import { cm } from "./messages";
import { useDuplicateCheck } from "./useDuplicateCheck";

export interface DuplicatePanelProps {
  org: string;
  matches: DuplicateMatch[];
  /** Opens the merge dialog (B-01-T17); the button is hidden until it is given. */
  onMerge?: (match: DuplicateMatch) => void;
}

function reasonText(fm: FormatMessage, reason: DuplicateReason, match: DuplicateMatch): string {
  switch (reason) {
    case "bn":
      return fm(cm.reasonBn);
    case "tax_id":
      return fm(cm.reasonTaxId);
    case "email":
      return fm(cm.reasonEmail);
    case "name":
      return fm(cm.reasonName, { percent: Math.round((match.similarity ?? 0) * 100) });
  }
}

/**
 * "Possible duplicates" panel (B-01-T16, wireframe 13 marker 4): existing contacts that look like
 * the one being typed, each with why it matched (Business Number, tax ID, email, name similarity),
 * its number and province (the same name in another province is listed so people can tell), and
 * Open · Merge… · Ignore. A warning, never a block. The count is announced once to screen readers
 * (a polite status that changes only when the count changes, not on every keystroke).
 */
export function DuplicatePanel({ org, matches, onMerge }: DuplicatePanelProps) {
  const fm = useFormatMessage();
  const headingId = useId();
  const [ignored, setIgnored] = useState<ReadonlySet<string>>(new Set());
  const visible = matches.filter((match) => !ignored.has(match.contact.id));

  return (
    <>
      <p role="status" aria-live="polite" className="sr-only">
        {visible.length > 0 ? fm(cm.duplicatesAnnounce, { count: visible.length }) : ""}
      </p>
      {visible.length > 0 && (
        <section
          aria-labelledby={headingId}
          data-testid="duplicate-panel"
          className="rounded-lg border border-border-strong bg-surface-warning-subtle p-4"
        >
          <h2 id={headingId} className="text-sm font-semibold text-fg-warning">
            {fm(cm.duplicatesTitle, { count: visible.length })}
          </h2>
          <p className="mt-1 text-xs text-fg-warning">{fm(cm.duplicatesIntro)}</p>
          <ul className="mt-3 divide-y divide-border-strong">
            {visible.map((match) => {
              const { contact } = match;
              return (
                <li key={contact.id} className="py-2">
                  <p className="text-sm font-semibold text-fg">
                    {contact.display_name}
                    <span className="ml-1 font-normal text-fg-muted">
                      {fm(cm.contactMeta, {
                        number: contact.number,
                        province: contact.province || fm(cm.noProvince),
                      })}
                    </span>
                    {contact.archived && (
                      <Badge tone="neutral" className="ml-2">
                        {fm(cm.archived)}
                      </Badge>
                    )}
                  </p>
                  <p className="text-xs text-fg-muted">
                    {match.reasons.map((reason) => reasonText(fm, reason, match)).join(" · ")}
                  </p>
                  <div className="mt-1 flex flex-wrap gap-3">
                    <Link
                      href={`${orgModuleUrl(org, "contacts")}/${encodeURIComponent(contact.id)}`}
                      aria-label={fm(cm.open, { name: contact.display_name })}
                      className="text-sm font-semibold text-fg-link underline"
                    >
                      {fm(cm.openShort)}
                    </Link>
                    {onMerge && (
                      <Button
                        variant="link"
                        size="sm"
                        aria-label={fm(cm.mergeLabel, { name: contact.display_name })}
                        onClick={() => onMerge(match)}
                      >
                        {fm(cm.merge)}
                      </Button>
                    )}
                    <Button
                      variant="link"
                      size="sm"
                      aria-label={fm(cm.ignoreLabel, { name: contact.display_name })}
                      onClick={() => setIgnored((previous) => new Set(previous).add(contact.id))}
                    >
                      {fm(cm.ignore)}
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </>
  );
}

export interface LiveDuplicatePanelProps extends Omit<DuplicatePanelProps, "matches"> {
  /** What is being typed on the contact form: display name, email, BN, tax ID. */
  query: DuplicateQuery;
  delay?: number;
  fetcher?: typeof fetch;
}

/** The panel fed by the debounced live check — what the contact form mounts (B-01-T15). */
export function LiveDuplicatePanel({ query, delay, fetcher, ...props }: LiveDuplicatePanelProps) {
  const { matches } = useDuplicateCheck(props.org, query, { delay, fetcher });
  return <DuplicatePanel {...props} matches={matches} />;
}
