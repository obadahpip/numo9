"use client";

/**
 * A staff member's activity (V-05-T08): the 12-month heatmap of their audit-log changes
 * (`GET …/staff/<user>/activity`, V-05-T07) — colour scale, the number in each square's
 * tooltip, and the table alternative. Hidden for people who don't manage staff.
 */
import { ActivityHeatmap, formatDate, type ActivityHeatmapLabels, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { activityApi, type Activity } from "./api";
import { m } from "./messages";

export function StaffActivity({ practice, user }: { practice: string; user: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [activity, setActivity] = useState<Activity | null>(null);
  useEffect(() => {
    let cancelled = false;
    void activityApi.get(practice, user).then((result) => {
      if (!cancelled && result.status === 200 && Array.isArray(result.body?.days))
        setActivity(result.body);
    });
    return () => {
      cancelled = true;
    };
  }, [practice, user]);
  const labels = useMemo<ActivityHeatmapLabels | null>(() => {
    if (!activity) return null;
    const day = (date: string) => formatDate(date as never, { locale });
    return {
      chart: fm(m.activityChart, { total: activity.total }),
      less: fm(m.activityLess),
      more: fm(m.activityMore),
      showTable: fm(m.activityTable),
      showChart: fm(m.activityChartToggle),
      tableDate: fm(m.activityDate),
      tableCount: fm(m.activityCount),
      day: (count, date) => fm(m.activityDay, { count, date: day(date) }),
      date: day,
      empty: fm(m.activityEmpty),
    };
  }, [activity, fm, locale]);
  if (!activity || !labels) return null;
  return (
    <section className="flex flex-col gap-2" aria-labelledby="staff-activity-heading">
      <h2 id="staff-activity-heading" className="text-lg font-semibold text-fg">
        {fm(m.activityTitle)}
      </h2>
      <ActivityHeatmap days={activity.days} from={activity.from} to={activity.to} labels={labels} />
    </section>
  );
}
