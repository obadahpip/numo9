import { AppShell } from "@/components/AppShell";
import { CatalogueNav } from "@/console/shell/CatalogueNav";
import { ConsoleFrame } from "@/console/shell/ConsoleFrame";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";
import { PackageEditor } from "@/packages/PackageEditor";

const messages = defineMessages({
  crumb: {
    id: "console.packages.editCrumb",
    defaultMessage: "Platform console · Package",
    description: "Breadcrumb of the package editor",
  },
});

/** Platform console → one package (U-02-T09, T10), `/console/packages/<code>`. */
export default async function PackagePage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(messages.crumb)}>
      <ConsoleFrame current="/console/packages">
        <div className="flex flex-col gap-4">
          <CatalogueNav current="/console/packages" />
          <PackageEditor code={decodeURIComponent(code)} />
        </div>
      </ConsoleFrame>
    </AppShell>
  );
}
