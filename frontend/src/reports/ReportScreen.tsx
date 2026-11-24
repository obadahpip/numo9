"use client";

/** One report's page (K-01-T13…T15): the runner, with the drill drawer and the layout editor. */
import { DrillDrawer } from "./DrillDrawer";
import { ReportRunner } from "./ReportRunner";

export function ReportScreen({ org, slug }: { org: string; slug: string }) {
  return (
    <ReportRunner
      org={org}
      slug={slug}
      renderDrill={(target, body, close) => (
        <DrillDrawer org={org} report={slug} target={target} body={body} onClose={close} />
      )}
    />
  );
}
