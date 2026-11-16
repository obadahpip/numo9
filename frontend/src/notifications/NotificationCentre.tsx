"use client";

import {
  Button,
  Drawer,
  ErrorState,
  formatDate,
  formatTime,
  LoadingRegion,
  SkeletonText,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import {
  listNotifications,
  markAllRead,
  markRead,
  notifyNotificationsChanged,
  type AppNotification,
} from "./api";

export const centreMessages = defineMessages({
  bell: {
    id: "notifications.bell",
    defaultMessage:
      "{count, plural, =0 {Notifications} one {Notifications, # unread} other {Notifications, # unread}}",
    description: "Accessible name of the bell button in the top bar, with the unread count",
  },
  announce: {
    id: "notifications.announce",
    defaultMessage:
      "{count, plural, one {You have # unread notification.} other {You have # unread notifications.}}",
    description: "Read out by screen readers when new notifications arrive",
  },
  title: {
    id: "notifications.title",
    defaultMessage: "Notifications",
    description: "Drawer title",
  },
  description: {
    id: "notifications.description",
    defaultMessage: "What happened in this organisation that concerns you.",
    description: "Text under the drawer title",
  },
  close: {
    id: "notifications.close",
    defaultMessage: "Close notifications",
    description: "Accessible name of the drawer's close button",
  },
  markAll: {
    id: "notifications.markAll",
    defaultMessage: "Mark all as read",
    description: "Button that marks every unread notification read",
  },
  settings: {
    id: "notifications.settings",
    defaultMessage: "Notification settings",
    description: "Link to the notification preferences page",
  },
  empty: {
    id: "notifications.empty",
    defaultMessage:
      "You're all caught up. Notifications about jobs, documents, approvals and your account appear here.",
    description: "Drawer when the person has no notifications",
  },
  loading: {
    id: "notifications.loading",
    defaultMessage: "Loading notifications…",
    description: "Accessible name of the loading skeleton",
  },
  loadFailed: {
    id: "notifications.loadFailed",
    defaultMessage: "Notifications couldn't be loaded",
    description: "Error title",
  },
  loadFailedBody: {
    id: "notifications.loadFailedBody",
    defaultMessage: "Check your connection, then try again.",
    description: "Error body",
  },
  retry: { id: "notifications.retry", defaultMessage: "Try again", description: "Retry button" },
  more: {
    id: "notifications.more",
    defaultMessage: "Show older notifications",
    description: "Loads the next page",
  },
  today: { id: "notifications.today", defaultMessage: "Today", description: "Day heading" },
  yesterday: {
    id: "notifications.yesterday",
    defaultMessage: "Yesterday",
    description: "Day heading",
  },
  unread: {
    id: "notifications.unread",
    defaultMessage: "Unread: ",
    description: "Screen-reader prefix of an unread notification's title",
  },
  meta: {
    id: "notifications.meta",
    defaultMessage: "{category} · {time}",
    description: "Category and time of a notification",
  },
  markOneFor: {
    id: "notifications.markOneFor",
    defaultMessage: "Mark as read: {title}",
    description: "Accessible name of the Mark as read button of one notification",
  },
  markOne: {
    id: "notifications.markOne",
    defaultMessage: "Mark as read",
    description: "Button on one unread notification",
  },
});

type Locale = "en-CA" | "fr-CA";

function dayKey(iso: string): string {
  const date = new Date(iso);
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

/** Notifications grouped by local day, newest day first (the list is newest first already). */
export function groupByDay(items: AppNotification[]): { key: string; items: AppNotification[] }[] {
  const groups: { key: string; items: AppNotification[] }[] = [];
  for (const item of items) {
    const key = dayKey(item.created_at);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.items.push(item);
    else groups.push({ key, items: [item] });
  }
  return groups;
}

interface NotificationCentreProps {
  org: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The server's unread count after a change (the bell updates at once). */
  onCount: (count: number) => void;
}

/**
 * Notification centre drawer (A-07-T09): the person's notifications in the organisation grouped
 * by day (Today, Yesterday, then dates), unread ones marked; opening one marks it read and goes
 * to its page; "Mark all as read"; older pages on demand; a link to the preferences page.
 */
export function NotificationCentre({
  org,
  open,
  onOpenChange,
  onCount,
}: Readonly<NotificationCentreProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as Locale;
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (before?: string) => {
      setFailed(false);
      const answer = await listNotifications(org, { before });
      if (answer.status !== 200 || !Array.isArray(answer.body.results)) {
        setFailed(true);
        return;
      }
      setItems((current) =>
        before && current ? [...current, ...answer.body.results] : answer.body.results,
      );
      setNext(answer.body.next);
      onCount(answer.body.unread_count);
    },
    [org, onCount],
  );

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  const readOne = async (item: AppNotification) => {
    if (item.read) return;
    setItems(
      (current) => current?.map((n) => (n.id === item.id ? { ...n, read: true } : n)) ?? null,
    );
    await markRead(org, item.id);
    notifyNotificationsChanged();
  };

  const readAll = async () => {
    setBusy(true);
    const answer = await markAllRead(org);
    setBusy(false);
    if (answer.status === 200) {
      setItems((current) => current?.map((n) => ({ ...n, read: true })) ?? null);
      onCount(answer.body.unread_count);
      notifyNotificationsChanged();
    }
  };

  const today = dayKey(new Date().toISOString());
  const yesterday = dayKey(new Date(Date.now() - 86_400_000).toISOString());
  const dayLabel = (group: { key: string; items: AppNotification[] }) => {
    if (group.key === today) return fm(centreMessages.today);
    if (group.key === yesterday) return fm(centreMessages.yesterday);
    const first = group.items[0];
    return first ? formatDate(new Date(first.created_at), { locale }) : "";
  };
  const hasUnread = items?.some((n) => !n.read) ?? false;

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      size="sm"
      title={fm(centreMessages.title)}
      description={fm(centreMessages.description)}
      closeLabel={fm(centreMessages.close)}
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link
            className="text-fg-link underline"
            href={orgModuleUrl(org, "settings/notifications")}
            onClick={() => onOpenChange(false)}
          >
            {fm(centreMessages.settings)}
          </Link>
          <Button
            size="sm"
            variant="secondary"
            disabled={!hasUnread}
            loading={busy}
            onClick={() => void readAll()}
          >
            {fm(centreMessages.markAll)}
          </Button>
        </div>
      }
    >
      {failed ? (
        <ErrorState
          title={fm(centreMessages.loadFailed)}
          body={fm(centreMessages.loadFailedBody)}
          retryLabel={fm(centreMessages.retry)}
          onRetry={() => void load()}
        />
      ) : items === null ? (
        <LoadingRegion label={fm(centreMessages.loading)}>
          <SkeletonText lines={6} />
        </LoadingRegion>
      ) : items.length === 0 ? (
        <p className="text-fg-muted" data-notifications-empty>
          {fm(centreMessages.empty)}
        </p>
      ) : (
        <div className="flex flex-col gap-6">
          {groupByDay(items).map((group) => (
            <section key={group.key} aria-labelledby={`notifications-day-${group.key}`}>
              <h3
                id={`notifications-day-${group.key}`}
                className="mb-2 text-xs font-semibold tracking-wide text-fg-muted uppercase"
              >
                {dayLabel(group)}
              </h3>
              <ul className="flex flex-col divide-y divide-border">
                {group.items.map((item) => (
                  <NotificationItem
                    key={item.id}
                    item={item}
                    locale={locale}
                    onOpen={() => {
                      void readOne(item);
                      if (item.link) onOpenChange(false);
                    }}
                    onRead={() => void readOne(item)}
                  />
                ))}
              </ul>
            </section>
          ))}
          {next ? (
            <Button variant="secondary" size="sm" onClick={() => void load(next)}>
              {fm(centreMessages.more)}
            </Button>
          ) : null}
        </div>
      )}
    </Drawer>
  );
}

function NotificationItem({
  item,
  locale,
  onOpen,
  onRead,
}: Readonly<{ item: AppNotification; locale: Locale; onOpen: () => void; onRead: () => void }>) {
  const fm = useFormatMessage();
  const content = (
    <>
      <span className="flex items-start gap-2">
        {item.read ? null : (
          <span
            className="mt-1.5 size-2 shrink-0 rounded-full bg-surface-accent"
            aria-hidden="true"
          />
        )}
        <span className={item.read ? "text-fg" : "font-semibold text-fg"}>
          {item.read ? (
            item.title
          ) : (
            <>
              <span className="sr-only">{fm(centreMessages.unread)}</span>
              {item.title}
            </>
          )}
        </span>
      </span>
      {item.body ? <span className="text-sm text-fg-muted">{item.body}</span> : null}
      <span className="text-xs text-fg-muted">
        {fm(centreMessages.meta, {
          category: item.category_label,
          time: formatTime(item.created_at, { locale }),
        })}
      </span>
    </>
  );
  return (
    <li
      className="flex items-start justify-between gap-3 py-3"
      data-notification={item.id}
      data-read={item.read}
    >
      {item.link ? (
        <Link
          href={item.link}
          className="flex min-w-0 flex-col gap-1 hover:underline"
          onClick={onOpen}
        >
          {content}
        </Link>
      ) : (
        <div className="flex min-w-0 flex-col gap-1">{content}</div>
      )}
      {item.read ? null : (
        <Button
          size="sm"
          variant="ghost"
          onClick={onRead}
          aria-label={fm(centreMessages.markOneFor, { title: item.title })}
        >
          {fm(centreMessages.markOne)}
        </Button>
      )}
    </li>
  );
}

/**
 * Screen-reader announcement of new notifications (a polite live region): says the unread count
 * when it goes up after the first load — never on page load, never when it goes down.
 */
export function UnreadAnnouncer({ count }: Readonly<{ count: number | null }>) {
  const fm = useFormatMessage();
  const previous = useRef<number | null>(null);
  const [text, setText] = useState("");
  useEffect(() => {
    if (count !== null && previous.current !== null && count > previous.current) {
      setText(fm(centreMessages.announce, { count }));
    }
    previous.current = count;
  }, [count, fm]);
  return (
    <span role="status" aria-live="polite" className="sr-only" data-notifications-live>
      {text}
    </span>
  );
}
