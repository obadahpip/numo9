import { AppShell } from "@/components/AppShell";
import { FoundingScreen } from "@/console/founding/FoundingScreen";
import { m } from "@/console/founding/messages";
import { ConsoleFrame } from "@/console/shell/ConsoleFrame";
import { getFormatMessage } from "@/i18n/server";

/**
 * Platform console → Founding offer (U-08-T11), `/console/founding`: every platform user with
 * platform.console.view sees the counter and slots and may export them; releasing a place needs
 * platform.catalogue.manage (the API answers 403 otherwise).
 */
export default async function ConsoleFoundingPage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(m.crumb)}>
      <ConsoleFrame current="/console/founding">
        <FoundingScreen />
      </ConsoleFrame>
    </AppShell>
  );
}
