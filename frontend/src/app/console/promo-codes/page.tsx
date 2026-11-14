import { AppShell } from "@/components/AppShell";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";
import { ConsolePromoCodesScreen } from "@/packages/ConsolePromoCodesScreen";

const messages = defineMessages({
  crumb: {
    id: "console.promoCodes.crumb",
    defaultMessage: "Platform console · Promo codes",
    description: "Breadcrumb of the platform console's promo codes screen",
  },
});

/**
 * Platform console → Promo codes (U-02-T11), `/console/promo-codes`: platform owners only
 * (platform.catalogue.manage; anyone else gets the refusal panel from the API's 403).
 */
export default async function ConsolePromoCodesPage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(messages.crumb)}>
      <ConsolePromoCodesScreen />
    </AppShell>
  );
}
