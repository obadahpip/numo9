import { useId, type ReactNode } from "react";

import { cn } from "../primitives/cn";

/**
 * Why a screen or action isn't available (Phase 0 UX principles 3 and 4: zero silent redirects,
 * honest gating):
 * - `gated` — not in the organisation's package (402): name the package(s) that include it;
 * - `readOnly` — after a downgrade: data stays viewable;
 * - `permission` — the user's role doesn't allow it (403): who can grant it;
 * - `lock` — a lock date / period lock: the date and where to change it;
 * - `notFound` — missing or no longer accessible (404, also cross-organisation).
 */
export type ExplainKind = "gated" | "readOnly" | "permission" | "lock" | "notFound";

export interface ExplainPanelProps {
  kind: ExplainKind;
  /** What: "Payroll isn't in your package". */
  title: string;
  /** Why, and what stays possible: "It's included in Growth and Complete. Your data stays…". */
  body: ReactNode;
  /** Who can fix it: "Ask the organisation owner (Dana Lee) to upgrade." */
  fixer?: ReactNode;
  /** One-click actions: [Compare packages] [Ask the owner to upgrade]. */
  actions?: ReactNode[];
  /** Extra content (e.g. the 404 page search). */
  children?: ReactNode;
  /** h1 when the panel is the whole page (404, gated module), else h2. */
  headingLevel?: 1 | 2;
  className?: string;
}

const ICONS: Record<ExplainKind, ReactNode> = {
  gated: <path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z" />,
  readOnly: (
    <>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  permission: (
    <>
      <path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z" />
      <path d="M12 9v4M12 16h.01" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </>
  ),
  notFound: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5M8.5 11h5" />
    </>
  ),
};

const TONE: Record<ExplainKind, string> = {
  gated: "bg-surface-accent-subtle text-fg-accent-strong",
  readOnly: "bg-surface-info-subtle text-fg-info",
  permission: "bg-surface-warning-subtle text-fg-warning",
  lock: "bg-surface-warning-subtle text-fg-warning",
  notFound: "bg-surface-muted text-fg",
};

/**
 * Explain panel (A-10-T12): the honest refusal — what is unavailable, why, who can fix it and a
 * one-click way forward — instead of a redirect or a bare error code (F5 gated-feature flow,
 * microcopy §3.5).
 */
export function ExplainPanel({
  kind,
  title,
  body,
  fixer,
  actions = [],
  children,
  headingLevel = 2,
  className,
}: ExplainPanelProps) {
  const headingId = useId();
  const Heading = `h${headingLevel}` as const;
  return (
    <section
      aria-labelledby={headingId}
      data-explain={kind}
      className={cn(
        "mx-auto flex w-full max-w-xl flex-col gap-4 rounded-lg border border-border bg-surface p-6",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn("inline-flex size-12 items-center justify-center rounded-full", TONE[kind])}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          focusable="false"
        >
          {ICONS[kind]}
        </svg>
      </span>
      <div>
        <Heading
          id={headingId}
          className={cn("font-semibold text-fg", headingLevel === 1 ? "text-2xl" : "text-lg")}
        >
          {title}
        </Heading>
        <div className="mt-2 text-sm text-fg-muted">{body}</div>
        {fixer ? <div className="mt-2 text-sm text-fg">{fixer}</div> : null}
      </div>
      {children}
      {actions.length ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </section>
  );
}
