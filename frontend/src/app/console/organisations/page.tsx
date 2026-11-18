import { AppShell } from "@/components/AppShell";
import { OrganisationsScreen } from "@/console/organisations/OrganisationsScreen";
import { m } from "@/console/organisations/messages";
import { ConsoleFrame } from "@/console/shell/ConsoleFrame";
import { getFormatMessage } from "@/i18n/server";

/** Platform console → Organisations (U-06-T03/T04), `/console/organisations`. */
export default async function ConsoleOrganisationsPage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(m.crumb)}>
      <ConsoleFrame current="/console/organisations">
        <OrganisationsScreen />
      </ConsoleFrame>
    </AppShell>
  );
}
