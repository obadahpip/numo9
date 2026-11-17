import { AppShell } from "@/components/AppShell";
import { MetricsScreen } from "@/console/metrics/MetricsScreen";
import { m } from "@/console/metrics/messages";
import { ConsoleFrame } from "@/console/shell/ConsoleFrame";
import { getFormatMessage } from "@/i18n/server";

/** Platform console → Metrics (U-06-T06), `/console`: KPI tiles, trends and drill-downs. */
export default async function ConsoleMetricsPage() {
  const fm = await getFormatMessage();
  return (
    <AppShell section={fm(m.crumb)}>
      <ConsoleFrame current="/console">
        <MetricsScreen />
      </ConsoleFrame>
    </AppShell>
  );
}
