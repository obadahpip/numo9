import type { ReactNode } from "react";

export type NoticeTone = "danger" | "info" | "success" | "warning";

const TONES: Record<NoticeTone, string> = {
  danger: "border-border-danger bg-surface-danger-subtle text-fg",
  info: "border-border bg-surface-info-subtle text-fg",
  success: "border-border bg-surface-success-subtle text-fg",
  warning: "border-border bg-surface-warning-subtle text-fg",
};

/**
 * A message box on the authentication screens: a refused request (danger, announced at once
 * with `role="alert"`) or a status (`role="status"`). The text says what happened and what to
 * do (microcopy rules §3.5); colour is never the only signal — the words carry it.
 */
export function Notice({
  tone,
  children,
  id,
}: {
  tone: NoticeTone;
  children: ReactNode;
  id?: string;
}) {
  return (
    <div
      id={id}
      role={tone === "danger" ? "alert" : "status"}
      className={`mb-4 rounded-md border-2 px-4 py-3 text-sm ${TONES[tone]}`}
    >
      {children}
    </div>
  );
}
