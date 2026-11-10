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

/** Home outside an organisation: the design-system shell (A-10-T05) with a placeholder body. */
export default function HomePage() {
  return (
    <AppShell>
      <h1 className="text-2xl font-semibold">{formatMessage(messages.title)}</h1>
      <p className="mt-2 text-sm text-fg-muted">{formatMessage(messages.placeholder)}</p>
    </AppShell>
  );
}
