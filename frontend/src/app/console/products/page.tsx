import { ProductsScreen } from "@/catalogue/ProductsScreen";
import { AppShell } from "@/components/AppShell";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  crumb: {
    id: "console.products.crumb",
    defaultMessage: "Platform console · Products",
    description: "Breadcrumb of the platform console's Products screen",
  },
});

/**
 * Platform console → Products (U-01-T11), `/console/products`: the product catalogue for
 * platform staff (platform.catalogue.view; anyone else gets the refusal panel from the API's
 * 403). Package editing arrives with U-02, the rest of the console with U-06.
 */
export default async function ConsoleProductsPage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(messages.crumb)}>
      <ProductsScreen />
    </AppShell>
  );
}
