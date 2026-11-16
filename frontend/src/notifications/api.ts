/**
 * Client for the notification centre API (A-07-T01, T02; docs/architecture/notifications.md):
 * the signed-in person's own notifications and preferences in an organisation.
 * Every call resolves (never throws on an HTTP error): screens branch on `status`.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type Category =
  "system" | "security" | "jobs" | "documents" | "approvals" | "reminders" | "billing";

export interface AppNotification {
  id: string;
  category: Category;
  category_label: string;
  /** Rendered by the server in the reader's language. */
  title: string;
  body: string;
  title_key: string;
  link: string;
  read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationPage {
  results: AppNotification[];
  unread_count: number;
  next: string | null;
}

export interface Preference {
  category: Category;
  category_label: string;
  in_app: boolean;
  email: boolean;
  locked: boolean;
  is_default: boolean;
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/notifications`;

/** Fired after this tab changed notifications (read, read all) so every bell refreshes. */
export const NOTIFICATIONS_CHANGED_EVENT = "numo9:notifications-changed";

export function notifyNotificationsChanged(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT));
}

export function listNotifications(
  org: string,
  { before, unread }: { before?: string; unread?: boolean } = {},
): Promise<ApiResult<NotificationPage>> {
  const query = new URLSearchParams();
  if (before) query.set("before", before);
  if (unread) query.set("unread", "1");
  const suffix = query.size ? `?${query.toString()}` : "";
  return apiRequest<NotificationPage>(`${base(org)}${suffix}`);
}

export function unreadCount(org: string): Promise<ApiResult<{ unread_count: number }>> {
  return apiRequest<{ unread_count: number }>(`${base(org)}/unread-count`);
}

export function markRead(org: string, id: string): Promise<ApiResult<AppNotification>> {
  return apiRequest<AppNotification>(`${base(org)}/${encodeURIComponent(id)}/read`, {
    method: "POST",
  });
}

export function markAllRead(
  org: string,
): Promise<ApiResult<{ marked: number; unread_count: number }>> {
  return apiRequest<{ marked: number; unread_count: number }>(`${base(org)}/read-all`, {
    method: "POST",
    body: {},
  });
}

export function getPreferences(org: string): Promise<ApiResult<{ results: Preference[] }>> {
  return apiRequest<{ results: Preference[] }>(`${base(org)}/preferences`);
}

export function updatePreference(
  org: string,
  category: Category,
  change: { in_app?: boolean; email?: boolean },
): Promise<ApiResult<Preference>> {
  return apiRequest<Preference>(`${base(org)}/preferences`, {
    method: "PATCH",
    body: { category, ...change },
  });
}
