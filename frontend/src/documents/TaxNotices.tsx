"use client";

/**
 * Inline tax warnings above the totals (G-02-T08): a taxable sale into BC, SK or MB without its
 * PST registration (`tax.pos.pst_unregistered`), and a contact without a province — the
 * organisation's province is used (`missing_province`). Warnings only: saving is never blocked.
 */
import { defineMessages, useFormatMessage } from "@/i18n";

import type { TaxNotice } from "./useTaxDefaults";

const messages = defineMessages({
  title: {
    id: "documents.taxNotices.title",
    defaultMessage: "Tax notes",
    description: "Accessible name of the inline tax warnings (G-02-T08)",
  },
  pst: {
    id: "documents.taxNotices.pst",
    defaultMessage:
      "{count, plural, one {Line {lines} is a taxable sale} other {Lines {lines} are taxable sales}} into {province}, where you aren't registered for its PST: only GST is charged. Register for the PST to collect it.",
    description: "PST registration warning (G-02-T04)",
  },
  missing: {
    id: "documents.taxNotices.missingProvince",
    defaultMessage:
      "The contact has no province on file, so your organisation's province is used for {count, plural, one {line {lines}} other {lines {lines}}}. Add their address for the right tax.",
    description: "Missing-province hint (G-02-T03)",
  },
});

export function TaxNotices({ notices }: { notices: readonly TaxNotice[] }) {
  const fm = useFormatMessage();
  if (!notices.length) return null;
  return (
    <section
      aria-label={fm(messages.title)}
      className="rounded-md border border-border bg-surface-warning-subtle p-3 text-sm text-fg"
      data-tax-notices=""
    >
      <ul className="flex flex-col gap-1">
        {notices.map((notice) => (
          <li key={`${notice.code}-${notice.province}`} role="status" data-tax-notice={notice.code}>
            {fm(notice.code === "missing_province" ? messages.missing : messages.pst, {
              count: notice.lines.length,
              lines: notice.lines.join(", "),
              province: notice.province,
            })}
          </li>
        ))}
      </ul>
    </section>
  );
}
