"use client";

/**
 * Document warnings inline in an editor (G-03b-T12): the server's document-level warnings from
 * the live calculation — `REGISTRATION_STOPPED` for a document dated after a GST/HST or QST stop
 * that uses that registration's tax codes. A warning only: the document can still be saved.
 */
import { defineMessages, useFormatMessage } from "@/i18n";

import type { DocumentWarning } from "./api";

const messages = defineMessages({
  title: {
    id: "documents.warnings.title",
    defaultMessage: "Review before saving",
    description: "Heading of the editor's document warnings",
  },
});

export function DocumentWarnings({ warnings }: { warnings: DocumentWarning[] }) {
  const fm = useFormatMessage();
  if (!warnings.length) return null;
  return (
    <section
      aria-label={fm(messages.title)}
      className="rounded-md border border-border bg-surface-warning-subtle p-3 text-sm text-fg"
      data-document-warnings=""
    >
      <ul className="flex flex-col gap-1">
        {warnings.map((warning) => (
          <li key={warning.code} role="status" data-warning={warning.code}>
            {warning.message}
          </li>
        ))}
      </ul>
    </section>
  );
}
