import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { OrganisationDetailScreen } from "@/console/organisations/OrganisationDetailScreen";
import { m } from "@/console/organisations/messages";
import { ConsoleFrame } from "@/console/shell/ConsoleFrame";
import { getFormatMessage } from "@/i18n/server";

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Platform console → one organisation (U-06-T04), `/console/organisations/:id`. */
export default async function ConsoleOrganisationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!ID.test(id)) notFound();
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(m.detailCrumb)}>
      <ConsoleFrame current="/console/organisations">
        <OrganisationDetailScreen id={id} />
      </ConsoleFrame>
    </AppShell>
  );
}
