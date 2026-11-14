import { AppShell } from "@/components/AppShell";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";
import { PackagesScreen } from "@/packages/PackagesScreen";

const messages = defineMessages({
  crumb: {
    id: "console.packages.crumb",
    defaultMessage: "Platform console · Packages and prices",
    description: "Breadcrumb of the platform console's packages screen",
  },
});

/**
 * Platform console → Packages and prices (U-02-T09), `/console/packages`: the packages for
 * platform owners (platform.catalogue.manage; anyone else gets the refusal panel from the API's
 * 403). The console shell arrives with U-06 (U-06-T07 reuses these screens).
 */
export default async function ConsolePackagesPage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(messages.crumb)}>
      <PackagesScreen />
    </AppShell>
  );
}
