"use client";

/** One report's page (K-01-T13): the runner, with the drill drawer and the layout editor. */
import { ReportRunner } from "./ReportRunner";

export function ReportScreen({ org, slug }: { org: string; slug: string }) {
  return <ReportRunner org={org} slug={slug} />;
}
