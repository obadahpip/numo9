import { AppShell } from "@/components/AppShell";
import { ConsoleJobsScreen } from "@/console/jobs/ConsoleJobsScreen";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  crumb: {
    id: "console.jobs.crumb",
    defaultMessage: "Platform console · Background jobs",
    description: "Breadcrumb of the platform console's job dashboard",
  },
});

/**
 * Platform console → Background jobs (A-08-T08), `/console/jobs`: queues, failures, retry and
 * purge for platform staff (platform.jobs.view / platform.jobs.manage; anyone else gets the
 * refusal panel from the API's 403). The rest of the console arrives with U-06.
 */
export default async function ConsoleJobsPage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(messages.crumb)}>
      <ConsoleJobsScreen />
    </AppShell>
  );
}
