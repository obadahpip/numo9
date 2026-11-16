"use client";

import { ErrorState, LoadingRegion, SkeletonTable, Switch } from "@numo9/ui";
import { useCallback, useEffect, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { getPreferences, updatePreference, type Category, type Preference } from "./api";

const messages = defineMessages({
  title: {
    id: "notifications.prefs.title",
    defaultMessage: "Notifications",
    description: "Heading of the notification preferences page",
  },
  intro: {
    id: "notifications.prefs.intro",
    defaultMessage:
      "Choose how Numo9 tells you about things in this organisation. Your choices apply to you only, and only here.",
    description: "Text under the heading",
  },
  category: { id: "notifications.prefs.category", defaultMessage: "About", description: "Column" },
  inApp: { id: "notifications.prefs.inApp", defaultMessage: "In the app", description: "Column" },
  email: { id: "notifications.prefs.email", defaultMessage: "By email", description: "Column" },
  inAppFor: {
    id: "notifications.prefs.inAppFor",
    defaultMessage: "{category}: in the app",
    description: "Accessible name of a switch",
  },
  emailFor: {
    id: "notifications.prefs.emailFor",
    defaultMessage: "{category}: by email",
    description: "Accessible name of a switch",
  },
  locked: {
    id: "notifications.prefs.locked",
    defaultMessage: "Always on: you need to know about sign-ins and changes to your account.",
    description: "Note on the security row, whose switches can't be changed",
  },
  saved: {
    id: "notifications.prefs.saved",
    defaultMessage: "Saved: {category}.",
    description: "Announced after a switch changed",
  },
  saveFailed: {
    id: "notifications.prefs.saveFailed",
    defaultMessage: "{category} couldn't be saved. Try again.",
    description: "A switch change failed",
  },
  loading: {
    id: "notifications.prefs.loading",
    defaultMessage: "Loading your notification choices…",
    description: "Loading state",
  },
  loadFailed: {
    id: "notifications.prefs.loadFailed",
    defaultMessage: "Your notification choices couldn't be loaded",
    description: "Error title",
  },
  loadFailedBody: {
    id: "notifications.prefs.loadFailedBody",
    defaultMessage: "Verify your connection, then try again.",
    description: "Error body",
  },
  retry: { id: "notifications.prefs.retry", defaultMessage: "Try again", description: "Retry" },
});

/**
 * Settings → Notifications (A-07-T09): one row per category, a switch for the app and one for
 * email; a change saves at once and is announced. Security is locked on (greyed, with why).
 */
export function NotificationPreferencesScreen({ org }: Readonly<{ org: string }>) {
  const fm = useFormatMessage();
  const [rows, setRows] = useState<Preference[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [status, setStatus] = useState<{ text: string; error: boolean } | null>(null);

  const load = useCallback(async () => {
    setFailed(false);
    const answer = await getPreferences(org);
    if (answer.status === 200 && Array.isArray(answer.body.results)) setRows(answer.body.results);
    else setFailed(true);
  }, [org]);

  useEffect(() => {
    void load();
  }, [load]);

  const change = async (row: Preference, field: "in_app" | "email", value: boolean) => {
    setRows(
      (current) =>
        current?.map((r) => (r.category === row.category ? { ...r, [field]: value } : r)) ?? null,
    );
    const answer = await updatePreference(org, row.category as Category, { [field]: value });
    if (answer.status === 200) {
      setRows(
        (current) => current?.map((r) => (r.category === row.category ? answer.body : r)) ?? null,
      );
      setStatus({ text: fm(messages.saved, { category: row.category_label }), error: false });
    } else {
      setRows(
        (current) =>
          current?.map((r) => (r.category === row.category ? { ...r, [field]: !value } : r)) ??
          null,
      );
      setStatus({ text: fm(messages.saveFailed, { category: row.category_label }), error: true });
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{fm(messages.title)}</h1>
        <p className="text-fg-muted">{fm(messages.intro)}</p>
      </header>
      <p
        role="status"
        aria-live="polite"
        className={status?.error ? "text-fg-danger" : "text-fg-muted"}
        data-prefs-status
      >
        {status?.text ?? ""}
      </p>
      {failed ? (
        <ErrorState
          title={fm(messages.loadFailed)}
          body={fm(messages.loadFailedBody)}
          retryLabel={fm(messages.retry)}
          onRetry={() => void load()}
        />
      ) : rows === null ? (
        <LoadingRegion label={fm(messages.loading)}>
          <SkeletonTable rows={7} columns={3} />
        </LoadingRegion>
      ) : (
        <table className="w-full max-w-2xl text-start">
          <thead>
            <tr className="border-b border-border text-sm text-fg-muted">
              <th scope="col" className="py-2 text-start font-medium">
                {fm(messages.category)}
              </th>
              <th scope="col" className="w-28 py-2 text-center font-medium">
                {fm(messages.inApp)}
              </th>
              <th scope="col" className="w-28 py-2 text-center font-medium">
                {fm(messages.email)}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.category}
                className="border-b border-border"
                data-category={row.category}
              >
                <th scope="row" className="py-3 text-start font-normal">
                  <span className="block">{row.category_label}</span>
                  {row.locked ? (
                    <span className="block text-sm text-fg-muted">{fm(messages.locked)}</span>
                  ) : null}
                </th>
                <td className="py-3 text-center">
                  <Switch
                    aria-label={fm(messages.inAppFor, { category: row.category_label })}
                    checked={row.in_app}
                    disabled={row.locked}
                    onCheckedChange={(value) => void change(row, "in_app", value)}
                  />
                </td>
                <td className="py-3 text-center">
                  <Switch
                    aria-label={fm(messages.emailFor, { category: row.category_label })}
                    checked={row.email}
                    disabled={row.locked}
                    onCheckedChange={(value) => void change(row, "email", value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
