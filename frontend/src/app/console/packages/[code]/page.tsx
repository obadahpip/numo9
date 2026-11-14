import { AppShell } from "@/components/AppShell";
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
      <PackageEditor code={decodeURIComponent(code)} />
    </AppShell>
  );
}
