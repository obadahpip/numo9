import { AppShell } from "@/components/AppShell";
import { CatalogueNav } from "@/console/shell/CatalogueNav";
import { ConsoleFrame } from "@/console/shell/ConsoleFrame";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";
import { PackageEditor } from "@/packages/PackageEditor";

const messages = defineMessages({
  crumb: {
    id: "console.packages.newCrumb",
    defaultMessage: "Platform console · New package",
    description: "Breadcrumb of the package editor for a new package",
  },
});

/** Platform console → New package (U-02-T09), `/console/packages/new`. */
export default async function NewPackagePage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(messages.crumb)}>
      <ConsoleFrame current="/console/packages">
        <div className="flex flex-col gap-4">
          <CatalogueNav current="/console/packages" />
          <PackageEditor code={null} />
        </div>
      </ConsoleFrame>
    </AppShell>
  );
}
