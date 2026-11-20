import { AppShell } from "@/components/AppShell";
import { MetricsScreen } from "@/console/metrics/MetricsScreen";
import { DemoManagerPanel, FoundingCounterPanel } from "@/console/panels/ConsolePanels";
import { m } from "@/console/metrics/messages";
import { ConsoleFrame } from "@/console/shell/ConsoleFrame";
import { getFormatMessage } from "@/i18n/server";

/**
 * Platform console → Metrics (U-06-T06), `/console`: KPI tiles, trends and drill-downs; then the
 * founding counter and the demo manager panels (U-06-T13).
 */
export default async function ConsoleMetricsPage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(m.crumb)}>
      <ConsoleFrame current="/console">
        <div className="flex flex-col gap-6">
          <MetricsScreen />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <FoundingCounterPanel />
            <div className="lg:col-span-2">
              <DemoManagerPanel />
            </div>
          </div>
        </div>
      </ConsoleFrame>
    </AppShell>
  );
}
