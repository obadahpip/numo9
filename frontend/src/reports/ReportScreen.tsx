"use client";

/** One report's page (K-01-T13…T15): the runner, with the drill drawer and the layout editor.
 * A tax report's figure (G-05-T10) opens the tax detail for its code, or its document. */
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { DrillDrawer } from "./DrillDrawer";
import { LayoutEditor } from "./LayoutEditor";
import { ReportRunner } from "./ReportRunner";
import { taxDrillHref } from "./tax/TaxPanel";

function Navigate({ href, onDone }: { href: string; onDone: () => void }) {
  const router = useRouter();
  useEffect(() => {
    router.push(href);
    onDone();
  }, [router, href, onDone]);
  return null;
}

export function ReportScreen({ org, slug }: { org: string; slug: string }) {
  return (
    <ReportRunner
      org={org}
      slug={slug}
      renderDrill={(target, body, close) => {
        const tax = taxDrillHref(org, target.row);
        return tax ? (
          <Navigate href={tax} onDone={close} />
        ) : (
          <DrillDrawer org={org} report={slug} target={target} body={body} onClose={close} />
        );
      }}
      renderLayoutEditor={({ report, body, params, close, reload }) => (
        <LayoutEditor
          org={org}
          report={report}
          body={body}
          params={params}
          onClose={close}
          onSaved={(layout) => reload(layout || undefined)}
        />
      )}
    />
  );
}
