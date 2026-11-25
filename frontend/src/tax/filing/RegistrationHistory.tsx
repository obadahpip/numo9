"use client";

/** Stop / restart history of a registration (G-03b-T11, wireframe 70): each with its person. */
import { formatDate, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";

import { useFormatMessage } from "@/i18n";

import type { RegistrationEvent } from "./api";
import { frequencyLabels } from "./messages";
import { reasonLabels, smsg } from "./stopMessages";

export function RegistrationHistory({ events }: { events: RegistrationEvent[] }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  if (!events.length) return null;
  const day = (value: string) => formatDate(value, { locale });
  const at = (value: string) =>
    formatDate(new Date(value), { locale, timeZone: "America/Toronto" });
  return (
    <section aria-label={fm(smsg.historyTitle)} data-registration-history="">
      <h2 className="text-base font-semibold text-fg">{fm(smsg.historyTitle)}</h2>
      <ul className="mt-1 flex flex-col gap-1 text-sm text-fg">
        {events.map((event) => {
          const common = {
            date: day(event.date),
            hasNote: event.reason_text ? "yes" : "no",
            note: event.reason_text,
            name: event.by.name,
            at: at(event.at),
          };
          return (
            <li key={event.id} data-event={event.action}>
              {event.action === "stop"
                ? fm(smsg.historyStop, {
                    ...common,
                    reason: event.reason_code ? fm(reasonLabels[event.reason_code]) : "",
                  })
                : fm(smsg.historyRestart, {
                    ...common,
                    frequency: event.frequency ? fm(frequencyLabels[event.frequency]) : "",
                  })}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
