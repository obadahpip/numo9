import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ReportScreen } from "@/reports/ReportScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  report: string;
}

const SLUG = /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/;

/** Reports → one report (K-01-T13), `/o/:org/reports/:report`: the runner. */
export default async function ReportPage({ params }: { params: Promise<Params> }) {
  const { org, report } = await params;
  if (!ORG_SLUG.test(org) || !SLUG.test(report)) notFound();
  return (
    <AppShell org={org} modulePath="reports">
      <ReportScreen org={org} slug={report} />
    </AppShell>
  );
}
