# Documents and files (A-06)

| | |
|---|---|
| **Deliverable** | A-06 · Documents & file storage, Phase 0 (component A — platform) |
| **Branch** | `feature/A-06-documents-files` |
| **Code** | `backend/numo9/files/` (models, storage, filetypes, services, clamav, scanning, previews, inbound, inbound_email, attachments, listing, actions, api); `frontend/src/files/` (API client, upload, inbox, attachments panel, "create from file") |
| **Screen** | `/o/:org/documents` — Documents inbox |
| **Depends on** | A-01 (tenancy, row-level security, tenant sweep), A-02 (permissions), A-04 (audit), A-08 (jobs), A-10 (design system: DataGrid, StatusBadge, EmptyState) |
| **Used by** | B-01 (contact attachments), E-02 bills and E-04 expense claims ("create from file"), I-01 fixed assets, F bank statements (OFX/QFX/QBO, CSV), A-07 notifications (infected file), SP-03 email provider adapter |

Every file a person or an email brings in becomes a **document** of the organisation: stored
once, scanned for viruses before anyone can open it, previewed, tagged with a period and tax year,
and attachable to any record.

## Data

| Model | Table | What it is |
|---|---|---|
| `Document` | `files_document` | One stored file: key, name, type, size, SHA-256, status, source, sender, period, tax year, tags, folder, scan result, preview |
| `Attachment` | `files_attachment` | A document linked to a record (`record_type` = model label, `record_id` = public id) |
| `InboundMessage` | `files_inboundmessage` | One email received at the inbox address (idempotent by Message-ID) |
| `InboundAddress` | `files_inboundaddress` | The organisation's inbox address token (one active; a rotated one is accepted 7 more days) |

`Document`, `Attachment` and `InboundMessage` are organisation records (`OrgOwnedModel`) with
row-level security; `InboundAddress` is not under RLS because mail is routed by token before an
organisation is known. Columns: [data dictionary](../reference/data-dictionary.md#files).

Document statuses: `uploading` → `scanning` → `clean` (ready) or `infected` (quarantined).
Only `clean` documents are served.

## Storage (A-06-T02)

- S3-compatible buckets through django-storages: **files** (`NUMO9_FILES_BUCKET`) and
  **quarantine** (`NUMO9_FILES_QUARANTINE_BUCKET`); MinIO in the dev stack, any S3 in production
  (`NUMO9_FILES_S3_ENDPOINT_URL`, `NUMO9_FILES_S3_REGION`, credentials from the environment).
- Keys are always under the organisation's prefix: `org/<organisation public id>/YYYY/MM/<uuid>/<safe name>`;
  previews and thumbnails sit next to the file under `derived/`. `check_key` refuses any key outside
  the active organisation's prefix (or with `..`).
- Files are never served by Numo9: the browser gets a **signed URL valid 5 minutes** (SigV4,
  `X-Amz-Expires=300`), only for a clean document of the active organisation.
- `manage.py files_buckets` creates the buckets (dev, CI).

## Upload (A-06-T03)

1. `POST files/uploads {name, size}` checks the extension and the 25 MB limit and creates the
   document (`uploading`) with a **presigned POST** form (content-length-range enforced by S3).
2. The browser posts the file **straight to the bucket** (progress shown).
3. `POST files/<id>/finalize` reads the object: real size, SHA-256, type by **libmagic** matched
   against the extension (zip parts for XLSX/DOCX, text checks for CSV/OFX/QFX/QBO). A mismatch is
   refused (415) and the object deleted. Then the duplicate check and the virus scan are queued.

Accepted: PDF, PNG, JPEG, HEIC/HEIF, TIFF, CSV, XLSX, DOCX, OFX, QFX, QBO.

## Virus scan (A-06-T04)

Celery task `numo9.files.scan_document` (queue IO, retried up to 8 times while clamd is down)
streams the object to **clamd** (`INSTREAM`, `NUMO9_CLAMD_HOST`/`PORT`). Clean → `clean`, preview
queued. Infected → the object is **moved to the quarantine bucket**, the document becomes
`infected` with the signature, the event `files.document.quarantined` is recorded and the uploader
and the owners are emailed.

## Previews (A-06-T05)

`numo9.files.make_preview`: PDF first page (pypdfium2) and images incl. HEIC (Pillow +
pillow-heif, EXIF orientation applied) → JPEG preview (1600 px) and thumbnail (256 px).
Password-protected PDFs are marked `password`; other types `unsupported`.

## Email inbox (A-06-T06, T07)

- Address: `docs+<token>@<NUMO9_INBOUND_DOMAIN>`; 12-character token without look-alike
  characters, unique and never reused. **Rotate** makes a new address; the old one keeps working
  for 7 days.
- Webhook `POST /api/v1/inbound/email` (public, no session): the raw RFC 822 message, signed with
  **HMAC-SHA256** over `timestamp.body` (`X-Numo9-Timestamp`, `X-Numo9-Signature`,
  `NUMO9_INBOUND_WEBHOOK_SECRET`, 5-minute window). Bad signature → 403; otherwise 202. The
  provider adapter (SP-03) translates the chosen provider's format to this contract.
- The message is stored once per Message-ID; job `numo9.files.process_inbound` makes **one
  document per attachment**. Senders that are neither members nor contact people are accepted and
  flagged "unknown sender". Refused attachments are listed on the message and in its audit event.

## Duplicates (A-06-T08)

Same SHA-256 in the organisation (under an advisory lock) → the new copy is dropped and the
existing document returned (`duplicate: true`); `files.document.duplicate_received` records who
sent it again.

## Attachments (A-06-T09, T13)

`files/attachments` lists (`record_type`, `record_id`), attaches and detaches (soft delete) a
document on any `OrgOwnedModel` record of the organisation. The **Attachments panel**
(`frontend/src/files/AttachmentsPanel.tsx`) is the one component for every detail page: list,
download, remove, attach (upload then link), drop files on it, read-only without edit rights.

## Tagging, folders, bulk (A-06-T10)

`period` (YYYY-MM), `tax_year`, up to 20 custom tags (case-insensitive filter), folder
`inbox`/`archived`. `GET files` filters by folder, status, source, period, tax year, tag, text,
with a keyset cursor (limit ≤ 1,000). `POST files/bulk` applies one action to up to 1,000
documents in one audit batch: archive, unarchive, add/remove tags, set period, set tax year.

## "Create from file" (A-06-T11)

Modules register actions (`numo9.files.actions.register_file_action`). Until a module ships, its action is
listed greyed with the reason: bill (E-02), expense claim (E-04), fixed asset (I-01).

## Documents inbox (A-06-T12)

`/o/:org/documents`: drag files anywhere or press **U** to upload (per-file progress, refused
types and sizes said before sending); the inbox address with **Copy**; Inbox / Archived tabs; a
virtualised DataGrid of up to 1,000 documents (search, filter chips for source, period, tax year
and status, tag filter, unknown senders flagged); bulk archive and **Tag…** (tags, period, tax
year); the previewer beside the list (preview image, details, edit, download, "create from
file"). The list refreshes every 3 s while a document is uploading or being scanned. Playwright:
1,000 files paint in under 1 s (`frontend/e2e/documents-inbox.spec.ts`).

The files bucket origin must be allowed by the CSP: `NUMO9_CSP_STORAGE_SRC`
([security baseline](../security/security-baseline.md)).

## Permissions

| Key | Allows |
|---|---|
| `documents.file.view` | See documents and attachments, open signed URLs, see the inbox address |
| `documents.file.upload` | Upload |
| `documents.file.manage` | Edit, tag, archive, bulk, attach/detach, rotate the address |

Feature keys: `accounting.documents.read` (view), `accounting.documents.write` (changes; organisations without it skip inbound mail); `CORE` for the webhook endpoint.

## Isolation & security (A-06-T14)

`backend/tests/test_files_isolation.py` (marker `tenant_isolation`): the tenant sweep passes on
every files endpoint; another organisation's document id is 404 on detail, edit, finalize,
signed URL and actions; the signed URL service and `check_key` refuse other organisations'
documents and keys; bulk and attachments can't reach other organisations' documents or records;
raw SQL sees only the active organisation's rows.

## Audit (A-06-T15)

| Action | When |
|---|---|
| `files.document.created` / `.updated` | Upload started; finalize, scan, preview, edits, tags, folder |
| `files.document.duplicate_received` | The same file arrived again (on the existing document) |
| `files.document.quarantined` | A virus was found (signature in `meta`) |
| `files.document.downloaded` | The original was opened or downloaded (previews aren't logged) |
| `files.attachment.created` / `.deleted` | Attached to / removed from a record |
| `files.inboundaddress.created` / `.updated` | Address created; retired by a rotation |
| `files.inbound.processed` | An email was processed (sender, known or not, documents made, refused attachments) |
| Bulk operation | One batch per `files/bulk` call, each document's change inside it |

Tests: `backend/tests/test_files_audit.py`.

## Settings

| Setting | Default (dev) | Meaning |
|---|---|---|
| `NUMO9_FILES_BUCKET` | `numo9-files` | Files bucket |
| `NUMO9_FILES_QUARANTINE_BUCKET` | `numo9-quarantine` | Quarantine bucket |
| `NUMO9_FILES_S3_ENDPOINT_URL` | MinIO | S3 endpoint (empty = AWS) |
| `NUMO9_FILES_S3_REGION` | `hel1` | Region |
| `NUMO9_FILES_SIGNED_URL_SECONDS` | `300` | Signed URL lifetime |
| `NUMO9_CLAMD_HOST` / `NUMO9_CLAMD_PORT` | `clamav` / `3310` | Virus scanner |
| `NUMO9_INBOUND_DOMAIN` | `in.numo9.ca` | Inbox address domain |
| `NUMO9_INBOUND_WEBHOOK_SECRET` | — | Webhook signing secret (required to accept mail) |
| `NUMO9_CSP_STORAGE_SRC` (frontend) | — | Files bucket origin for the CSP |

## Limits of the Phase 0 build

- Tests use moto (S3 API) and a fake clamd speaking `INSTREAM`; moto doesn't enforce presigned
  URL expiry or content-length-range, so those are checked through the SigV4 parameters and at
  finalize. A test against a real ClamAV runs when `NUMO9_TEST_CLAMD_HOST` is set.
- The email provider is chosen in SP-03; until then the webhook contract is provider-neutral.
- The Attachments panel is mounted on the contact detail page when B-01's contact screens land.
