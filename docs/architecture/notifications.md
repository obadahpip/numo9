# Notifications and email (A-07)

| | |
|---|---|
| **Deliverable** | A-07 · Notifications, email & custom sending domain, Phase 0 (component A — platform) |
| **Branch** | `feature/A-07-notifications-email` |
| **Code** | `backend/numo9/notifications/` (models, texts, events, channels, services, serializers, api, urls) |
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

## Sending: `notify()` and preferences (A-07-T02)

Every module tells people about something through **one** call:

```python
from numo9.notifications.services import notify

notify("jobs.failed", [run.created_by], params={"job": label, "error": text},
       link=f"/o/{org.public_id}/jobs")
```

- **Events** (`numo9.notifications.events`): `register_event(key, category, title_key=…,
  channels=("in_app", "email"), mandatory=False)`. The event's category decides whose preferences
  apply; `title_key` is the message of the catalogue — the in-app notification stores it, the
  email renders it as subject and text. An unregistered key is refused (`UnknownEvent`).
- **Channels** (`numo9.notifications.channels`): `in_app` (a `Notification` row) and `email` (an
  email in the recipient's language, sent after the surrounding transaction commits — nothing on
  rollback; A-07-T03 queues it through Celery with retries and the message log). A channel nobody
  registered is skipped.
- **What each person gets** = the event's channels ∩ `channels=` (when given) ∩ the person's
  choice for the category in this organisation. *Mandatory* events (a new sign-in, a failed
  payment) skip the choice; duplicates and empty recipients are skipped. `notify()` returns
  `Sent` — `(recipient, channel, result)` per delivery.

**Preferences** — `NotificationPreference` (person × organisation × category: `in_app`, `email`;
data dictionary:
[`notifications_notificationpreference`](../reference/data-dictionary.md#notifications-notificationpreference)).
No row = the default:

| Category | In the app | By email | |
|---|---|---|---|
| Account and system | ✓ | ✓ | |
| Security | ✓ | ✓ | **locked** — cannot be turned off |
| Background jobs | ✓ | — | |
| Documents | ✓ | — | |
| Approvals | ✓ | ✓ | |
| Reminders | ✓ | — | |
| Billing and subscription | ✓ | ✓ | |

Preferences are per organisation: turning job emails off in one client's books does not change
another's. API: `GET notifications/preferences` (each category with `in_app`, `email`, `locked`,
`is_default`) and `PATCH notifications/preferences` `{"category", "in_app", "email"}` — a locked
category answers `409 notifications.category_locked`.

## Tests

| Task | Tests |
|---|---|
| T01 | `tests/test_notifications_api.py` |
| T02 | `tests/test_notifications_service.py` |
