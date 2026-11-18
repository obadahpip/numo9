import { AppShell } from "@/components/AppShell";
import { FlagsScreen } from "@/console/flags/FlagsScreen";
import { m } from "@/console/flags/messages";
import { ConsoleFrame } from "@/console/shell/ConsoleFrame";
import { getFormatMessage } from "@/i18n/server";

/** Platform console → Feature flags (U-06-T12), `/console/flags` (platform.flags.manage). */
export default async function ConsoleFlagsPage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(m.crumb)}>
      <ConsoleFrame current="/console/flags">
        <FlagsScreen />
      </ConsoleFrame>
    </AppShell>
  );
}
