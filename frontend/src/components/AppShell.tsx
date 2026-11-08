import type { ReactNode } from "react";

import { defineMessages, formatMessage } from "@/i18n";

const messages = defineMessages({
  brand: { id: "common.brand", defaultMessage: "Numo9", description: "Product name" },
  mainNav: {
    id: "shell.nav.main",
    defaultMessage: "Main",
    description: "Accessible name of the main navigation",
  },
});

/** Application shell placeholder (header, side navigation, main). Replaced by the A-10 shell. */
export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center border-b border-[var(--color-border)] px-6">
        <span className="text-lg font-semibold">{formatMessage(messages.brand)}</span>
      </header>
      <div className="flex flex-1">
        <nav
          aria-label={formatMessage(messages.mainNav)}
          className="w-56 border-e border-[var(--color-border)] p-4"
        />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
