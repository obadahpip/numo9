"use client";

/**
 * Dashboard widget "Dormant staff" (V-05-T06): the practice's members without a sign-in for the
 * practice's threshold (60 days by default) who can still open its clients, with one-click
 * *Suspend access*. Shown to people who manage the practice's staff; renders nothing otherwise
 * (or when nobody is dormant).
 */
import { Button } from "@numo9/ui";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { dormantApi, type DormantMember } from "./api";
import { m } from "./messages";

export function DormantStaffWidget({ practice }: { practice: string }) {
  const fm = useFormatMessage();
  const [days, setDays] = useState(60);
  const [staff, setStaff] = useState<DormantMember[] | null>(null);
  const [status, setStatus] = useState("");
  useEffect(() => {
    let cancelled = false;
    void dormantApi.list(practice).then((result) => {
      if (cancelled || result.status !== 200 || !Array.isArray(result.body?.staff)) return;
      setDays(result.body.dormant_days);
      setStaff(result.body.staff);
    });
    return () => {
      cancelled = true;
    };
  }, [practice]);
  if (!staff || staff.length === 0) {
    return status ? (
      <p role="status" className="text-sm text-fg-muted">
        {status}
      </p>
    ) : null;
  }
  return (
    <section
      aria-labelledby="dormant-staff-heading"
      className="flex flex-col gap-2 rounded-lg border border-border p-4"
      data-dormant-widget=""
    >
      <h2 id="dormant-staff-heading" className="text-base font-semibold text-fg">
        {fm(m.dormantTitle)}
      </h2>
      <p className="text-sm text-fg-muted">{fm(m.dormantIntro, { days })}</p>
      <ul className="flex flex-col divide-y divide-border">
        {staff.map((person) => {
          const name = person.name || person.email;
          return (
            <li key={person.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span className="text-sm">{fm(m.dormantLine, { name, days: person.days })}</span>
              <Button
                size="sm"
                variant="danger"
                onClick={() =>
                  void dormantApi.suspend(practice, person.id).then((result) => {
                    if (result.status !== 200) return;
                    setStaff((current) => (current ?? []).filter((p) => p.id !== person.id));
                    setStatus(fm(m.suspended, { name }));
                  })
                }
              >
                {fm(m.suspend, { name })}
              </Button>
            </li>
          );
        })}
      </ul>
      <p role="status" className="sr-only">
        {status}
      </p>
    </section>
  );
}
