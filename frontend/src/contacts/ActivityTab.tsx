"use client";

/** Contact → Activity (B-02-T10): the timeline newest first, filtered by type; add a note. */
import { Button, formatDateTime, formatMoney, Input, Select, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { activityApi, type ActivityEventRow } from "./activityApi";
import { tm } from "./tabMessages";

export function ActivityTab({ org, id }: { org: string; id: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [events, setEvents] = useState<ActivityEventRow[]>([]);
  const [types, setTypes] = useState<{ value: string; label: string }[]>([]);
  const [type, setType] = useState("all");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    const result = await activityApi.timeline(org, id, type === "all" ? undefined : type);
    if (result.status === 200) {
      setEvents(result.body.results);
      setTypes(result.body.types);
    }
  }, [org, id, type]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-4" data-activity-tab="">
      <div className="flex flex-wrap items-end gap-3">
        <Select
          aria-label={fm(tm.filter)}
          value={type}
          onValueChange={setType}
          options={[{ value: "all", label: fm(tm.allTypes) }, ...types]}
        />
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!note.trim()) return;
            void activityApi.note(org, id, note.trim()).then(() => {
              setNote("");
              void load();
            });
          }}
        >
          <Input
            aria-label={fm(tm.noteLabel)}
            placeholder={fm(tm.noteLabel)}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            className="w-64"
          />
          <Button type="submit">{fm(tm.addNote)}</Button>
        </form>
      </div>
      {events.length === 0 ? (
        <p className="text-sm text-fg-muted">{fm(tm.noActivity)}</p>
      ) : (
        <ol className="flex flex-col divide-y divide-border rounded-md border border-border">
          {events.map((event) => (
            <li
              key={event.id}
              className="flex flex-wrap justify-between gap-2 p-3 text-sm"
              data-type={event.type}
            >
              <span>
                {fm(tm.eventLine, {
                  when: formatDateTime(event.occurred_at, { locale }),
                  title: event.title,
                })}
                {event.by ? (
                  <span className="block text-xs text-fg-muted">
                    {fm(tm.by, { name: event.by })}
                  </span>
                ) : null}
              </span>
              {event.amount !== null ? (
                <span className="tabular-nums">{formatMoney(event.amount, { locale })}</span>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
