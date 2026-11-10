import type { ReactNode } from "react";

/**
 * Do / Don't pair for the Storybook usage docs (A-10-T20). Documentation only — not exported
 * from `@numo9/ui`.
 */
export function DoDont({ children }: { children: ReactNode }) {
  return <div className="my-4 grid gap-4 md:grid-cols-2">{children}</div>;
}

export function Do({ children }: { children: ReactNode }) {
  return (
    <section
      aria-label="Do"
      className="rounded-lg border-2 border-border bg-surface p-4 text-sm"
      style={{ borderColor: "var(--n9-color-green-700, #15803d)" }}
    >
      <p className="mb-2 font-semibold text-fg-success">✓ Do</p>
      <div className="space-y-2 text-fg">{children}</div>
    </section>
  );
}

export function Dont({ children }: { children: ReactNode }) {
  return (
    <section
      aria-label="Don't"
      className="rounded-lg border-2 border-border-danger bg-surface p-4 text-sm"
    >
      <p className="mb-2 font-semibold text-fg-danger">✗ Don’t</p>
      <div className="space-y-2 text-fg">{children}</div>
    </section>
  );
}
