# Notifications and email (A-07)

| | |
|---|---|
| **Deliverable** | A-07 · Notifications, email & custom sending domain, Phase 0 (component A — platform) |
| **Branch** | `feature/A-07-notifications-email` |
| **Code** | `backend/numo9/notifications/` (models, texts, services, serializers, api, urls) |
| **Depends on** | A-01 (tenancy), A-03 (permissions), A-08 (jobs, for email sending — A-07-T03) |
| **Used by** | A-08 job results, A-06 quarantined files, A-02 security events, U-04 billing, B-03 imports, approvals (C-04, E) |
| **Gaps** | gap-42 (branded email from the organisation's own domain — A-07-T04…T10) |

One notification service for in-app and email. This page grows with the deliverable; A-07-T01
adds the in-app notification store and API.

## Notification (A-07-T01)

`Notification` — one message to one person in one organisation (data dictionary:
[`notifications_notification`](../reference/data-dictionary.md#notifications-notification)):

| Field | Rule |
|---|---|
| `recipient` | The person it is for — nobody else lists, reads or marks it |
| `category` | `system`, `security`, `jobs`, `documents`, `approvals`, `reminders`, `billing` (preferences per category: A-07-T02) |
| `title_key` + `body_params` | A key of the message catalogue and its parameters — never rendered text, so the reader sees their own language at read time |
| `link` | A path inside the app (`/o/<org>/…`); another site, `//host` or a backslash is refused (model and database check `notifications_link_in_app`) |
| `read_at` | When it was read; empty = unread |

Not audited (personal, high-volume; the events themselves are audited where they happen); soft
delete from `OrgOwnedModel` hides a notification everywhere.

**Message catalogue** — `numo9.notifications.texts`: `register_text(key, title, body)` with named
`%(param)s` placeholders; `render(key, params, language)` gives `(title, body)` in that language;
a missing parameter renders empty and an unknown key as "Notification" (old notifications survive
a removed message). Phase 0 messages: `notifications.job.finished`, `notifications.job.failed`,
`notifications.document.quarantined`; A-07-T11 seeds the system catalogue.

**Services** — `numo9.notifications.services`: `my_notifications(user)`, `unread_count(user)`,
`mark_read(notification)` (idempotent: the first read time stays), `mark_all_read(user,
category=None)` — always for the active organisation.

## API (A-07-T01)

Under `/api/v1/o/<org>/`, permission `organisation.profile.view` (every role), feature `CORE`
(never gated). Another person's notification, another organisation's, or an unknown id: 404.

| Method and path | What |
|---|---|
| `GET notifications` | Newest first, 30 per page (`?limit=` 1–100), `?unread=1`, `?category=`, `?before=<id>` for the next page; `{"results": [...], "unread_count": n, "next": id or null}`. Each notification: `id`, `category` (+ `category_label`), `title`, `body` (rendered in the reader's language), `title_key`, `params`, `link`, `read`, `read_at`, `created_at` |
| `GET notifications/unread-count` | `{"unread_count": n}` — the bell's badge |
| `POST notifications/<id>/read` | Mark one read → the notification |
| `POST notifications/read-all` | `{"category": …}` optional → `{"marked": n, "unread_count": remaining}` |

## Tests

| Task | Tests |
|---|---|
| T01 | `tests/test_notifications_api.py` |
