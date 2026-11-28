"use client";

/**
 * "Create rule from this line" (F-04-T14) — a self-contained action for a statement line: drop
 * it into a row of the statement-lines list (F-02) with the row's line; it links to the rule
 * builder pre-filled from the line (``fromLine.ts``).
 *
 *     <CreateRuleFromLineAction org={org} line={line} />
 */
import Link from "next/link";

import { defineMessages, useFormatMessage } from "@/i18n";

import { ruleFromLineHref, type StatementLineLike } from "./fromLine";

const messages = defineMessages({
  label: {
    id: "bankRules.fromLine.label",
    defaultMessage: "Create rule from this line",
    description: "Action on a statement line",
  },
  named: {
    id: "bankRules.fromLine.named",
    defaultMessage: "Create a rule from {line}",
    description: "Accessible name of the action, with the line's payee or description",
  },
});

export interface CreateRuleFromLineActionProps {
  org: string;
  line: StatementLineLike;
  className?: string;
}

export function CreateRuleFromLineAction({ org, line, className }: CreateRuleFromLineActionProps) {
  const fm = useFormatMessage();
  const what = line.payee?.trim() || line.description?.trim() || "";
  return (
    <Link
      href={ruleFromLineHref(org, line)}
      aria-label={what ? fm(messages.named, { line: what }) : undefined}
      className={
        className ??
        "inline-flex min-h-touch-target items-center text-sm font-semibold text-fg-link underline underline-offset-2"
      }
      data-action="create-rule-from-line"
    >
      {fm(messages.label)}
    </Link>
  );
}
