import type { ReactNode } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

const messages = defineMessages({
  brand: { id: "common.brand", defaultMessage: "Numo9", description: "Product name" },
  tagline: {
    id: "common.tagline",
    defaultMessage: "Numbers build a brighter tomorrow",
    description: "Product tagline (page meta description)",
  },
});

/**
 * Frame of the public authentication screens (A-02-T10…T12): sign-up, verify, login, 2FA,
 * reset, invitation. One centred card on the page background, the Numo9 wordmark above it — no
 * app shell (the visitor has no organisation yet) and no promotional content (UX principle 15).
 * The card holds the screen's `h1`.
 */
export function AuthLayout({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const fm = useFormatMessage();
  return (
    <div className="flex min-h-screen flex-col items-center bg-surface-subtle px-4 py-8 sm:py-16">
      <header className="mb-6 text-center">
        <p className="inline-block rounded-md bg-surface-accent px-3 py-1 text-xl font-bold text-fg-on-accent">
          {fm(messages.brand)}
        </p>
        <p className="mt-2 text-sm text-fg-muted">{fm(messages.tagline)}</p>
      </header>
      <main
        id="main"
        className={`w-full ${wide ? "max-w-xl" : "max-w-md"} rounded-lg border border-border bg-surface p-6 shadow-elevation-1 sm:p-8`}
      >
        {children}
      </main>
    </div>
  );
}
