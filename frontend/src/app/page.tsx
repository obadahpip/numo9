import { AppShell } from "@/components/AppShell";
import { defineMessages, formatMessage } from "@/i18n";

const messages = defineMessages({
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
    <AppShell>
      <h1 className="text-2xl font-semibold">{formatMessage(messages.title)}</h1>
      <p className="mt-2 text-sm text-gray-600">{formatMessage(messages.placeholder)}</p>
    </AppShell>
  );
}
