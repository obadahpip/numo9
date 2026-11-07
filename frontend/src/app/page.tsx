import { defineMessages, formatMessage } from "@/i18n";

const messages = defineMessages({
  brand: { id: "common.brand", defaultMessage: "Numo9", description: "Product name" },
  mainNav: {
    id: "shell.nav.main",
    defaultMessage: "Main",
    description: "Accessible name of the main navigation",
  },
  title: { id: "home.title", defaultMessage: "Home", description: "Home page heading" },
  placeholder: {
    id: "home.placeholder",
    defaultMessage: "Application shell placeholder.",
    description: "Temporary body text until A-10 shell",
  },
});

/** Application shell placeholder. Replaced by the A-10 design-system shell. */
export default function HomePage() {
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
        <main className="flex-1 p-6">
          <h1 className="text-2xl font-semibold">{formatMessage(messages.title)}</h1>
          <p className="mt-2 text-sm text-gray-600">{formatMessage(messages.placeholder)}</p>
        </main>
      </div>
    </div>
  );
}
