import { AppShell } from "@/components/AppShell";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  title: { id: "home.title", defaultMessage: "Home", description: "Home page heading" },
  placeholder: {
    id: "home.placeholder",
    defaultMessage: "Application shell placeholder.",
    description: "Temporary body text until A-10 shell",
  },
});

/** Home outside an organisation: the design-system shell (A-10-T05) with a placeholder body. */
export default async function HomePage() {
  const fm = await getFormatMessage();
  return (
    <AppShell>
      <h1 className="text-2xl font-semibold">{fm(messages.title)}</h1>
      <p className="mt-2 text-sm text-fg-muted">{fm(messages.placeholder)}</p>
    </AppShell>
  );
}
