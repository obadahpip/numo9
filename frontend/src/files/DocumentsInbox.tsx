"use client";

import {
  Badge,
  Button,
  DataGrid,
  Dialog,
  EmptyState,
  ErrorState,
  formatDate,
  Input,
  StatusBadge,
  type AppLocale,
  type DataGridColumn,
  type DataGridLabels,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type DragEvent } from "react";

import { useFormatMessage, type FormatMessage } from "@/i18n";

import {
  filesApi,
  humanSize,
  type DocumentStatus,
  type FileDocument,
  type Folder,
  type InboundAddress,
} from "./api";
import { CreateFromFile } from "./CreateFromFile";
import { fm as m } from "./messages";
import { uploadFile, type UploadState } from "./upload";

/** The inbox loads a whole folder at once (up to 1,000) and filters it in the grid. */
export const PAGE_LIMIT = 1000;
/** While files are uploading or being scanned the list is refreshed this often. */
export const REFRESH_MS = 3000;

const STATUS_KEY = {
  uploading: "queued",
  scanning: "scanning",
  clean: "ready",
  infected: "infected",
} as const;

function statusLabel(t: FormatMessage, status: DocumentStatus): string {
  return t(
    {
      uploading: m.statusUploading,
      scanning: m.statusScanning,
      clean: m.statusClean,
      infected: m.statusInfected,
    }[status],
  );
}

function useGridLabels(): DataGridLabels {
  const t = useFormatMessage();
  return {
    grid: t(m.gridName),
    search: t(m.gridSearch),
    columns: t(m.gridColumns),
    density: t(m.gridDensity),
    comfortable: t(m.gridComfortable),
    compact: t(m.gridCompact),
    filterAll: t(m.gridAll),
    filterChip: (column, value) => t(m.gridChip, { column, value }),
    clearFilters: t(m.gridClear),
    selectAll: t(m.gridSelectAll),
    selectRow: (row) => t(m.gridSelectRow, { row }),
    selectedCount: (count) => t(m.gridSelected, { count }),
    clearSelection: t(m.gridClearSelection),
    resultCount: (shown, total) => t(m.gridResults, { shown, total }),
    loading: t(m.loading),
  };
}

export interface DocumentsInboxProps {
  org: string;
}

interface UploadRow {
  id: string;
  name: string;
  size: number;
  state: UploadState;
}

/**
 * Documents inbox (A-06-T12, Phase 0 plan §3.3 "Documents inbox"): drag files anywhere on the page
 * or press `U` to upload (progress per file, straight to the bucket), the inbox address to copy,
 * Inbox / Archived folders, a virtualised grid of up to 1,000 documents with search, filter chips
 * (status, source, period, tax year) and a tag filter, bulk archive and tagging, and a previewer
 * beside the list (preview image, details, tags, download, "create from file").
 */
export function DocumentsInbox({ org }: DocumentsInboxProps) {
  const t = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const labels = useGridLabels();
  const fileInput = useRef<HTMLInputElement>(null);
  const [folder, setFolder] = useState<Folder>("inbox");
  const [rows, setRows] = useState<FileDocument[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [openId, setOpenId] = useState<string | null>(null);
  const [tag, setTag] = useState("");
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [dragging, setDragging] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [tagging, setTagging] = useState<string[] | null>(null);

  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setStatus("loading");
      const result = await filesApi.list(org, { folder, limit: PAGE_LIMIT });
      if (result.status === 200 && Array.isArray(result.body.results)) {
        setRows(result.body.results);
        setStatus("ready");
      } else if (!quiet) {
        setStatus("error");
      }
    },
    [org, folder],
  );

  useEffect(() => {
    setSelected(new Set());
    setOpenId(null);
    void load();
  }, [load]);

  const busy = rows.some((row) => row.status === "scanning" || row.status === "uploading");
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => void load(true), REFRESH_MS);
    return () => clearInterval(timer);
  }, [busy, load]);

  const startUploads = useCallback(
    (files: FileList | File[]) => {
      const list = Array.from(files);
      const created = list.map((file, index) => ({
        id: `${Date.now()}-${index}-${file.name}`,
        name: file.name,
        size: file.size,
        state: { kind: "uploading", percent: 0 } as UploadState,
      }));
      setUploads((current) => [...created, ...current]);
      list.forEach((file, index) => {
        const id = created[index]!.id;
        void uploadFile(org, file, (state) =>
          setUploads((current) => current.map((u) => (u.id === id ? { ...u, state } : u))),
        ).then((state) => {
          if (state.kind === "done") void load(true);
        });
      });
    },
    [org, load],
  );

  // `U` uploads (Phase 0 plan §3.3 shortcut), unless typing in a field.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target?.closest("input, textarea, select, [contenteditable='true'], [role='dialog']") !==
        null;
      if (
        !typing &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        event.key.toLowerCase() === "u"
      ) {
        event.preventDefault();
        fileInput.current?.click();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const tags = useMemo(() => {
    const seen = new Map<string, string>();
    for (const row of rows)
      for (const value of row.tags)
        if (!seen.has(value.toLowerCase())) seen.set(value.toLowerCase(), value);
    return [...seen.values()].sort((a, b) => a.localeCompare(b));
  }, [rows]);

  const shown = useMemo(
    () =>
      tag
        ? rows.filter((row) => row.tags.some((value) => value.toLowerCase() === tag.toLowerCase()))
        : rows,
    [rows, tag],
  );

  const columns = useMemo<DataGridColumn<FileDocument>[]>(
    () => [
      {
        id: "name",
        header: t(m.colName),
        accessor: (row) => row.name,
        hideable: false,
        cell: (row) => <span className="truncate font-medium">{row.name}</span>,
      },
      {
        id: "from",
        header: t(m.colFrom),
        accessor: (row) => (row.source === "email" ? row.sender : row.uploaded_by),
        width: 240,
        cell: (row) => (
          <span className="flex items-center gap-2 truncate">
            <span className="truncate">
              {row.source === "email" ? row.sender : row.uploaded_by}
            </span>
            {row.source === "email" && !row.sender_known ? (
              <Badge tone="warning">{t(m.unknownSender)}</Badge>
            ) : null}
          </span>
        ),
      },
      {
        id: "source",
        header: t(m.colSource),
        accessor: (row) => row.source,
        width: 100,
        searchable: false,
        cell: (row) => (row.source === "email" ? t(m.sourceEmail) : t(m.sourceUpload)),
        filterOptions: [
          { value: "upload", label: t(m.sourceUpload) },
          { value: "email", label: t(m.sourceEmail) },
        ],
      },
      {
        id: "period",
        header: t(m.colPeriod),
        accessor: (row) => row.period,
        width: 110,
        filterOptions: [...new Set(rows.map((r) => r.period).filter(Boolean))]
          .sort()
          .map((value) => ({ value, label: value })),
      },
      {
        id: "taxYear",
        header: t(m.colTaxYear),
        accessor: (row) => (row.tax_year === null ? "" : String(row.tax_year)),
        width: 100,
        filterOptions: [...new Set(rows.map((r) => r.tax_year).filter((y) => y !== null))]
          .sort()
          .map((value) => ({ value: String(value), label: String(value) })),
      },
      {
        id: "tags",
        header: t(m.colTags),
        accessor: (row) => row.tags.join(", "),
        width: 200,
      },
      {
        id: "status",
        header: t(m.colStatus),
        accessor: (row) => row.status,
        width: 190,
        searchable: false,
        cell: (row) => (
          <StatusBadge status={STATUS_KEY[row.status]} label={statusLabel(t, row.status)} />
        ),
        filterOptions: (["scanning", "clean", "infected"] as const).map((value) => ({
          value,
          label: statusLabel(t, value),
        })),
      },
      {
        id: "added",
        header: t(m.colAdded),
        accessor: (row) => row.created_at,
        width: 130,
        searchable: false,
        cell: (row) => formatDate(new Date(row.created_at), { locale }),
      },
    ],
    [t, locale, rows],
  );

  const bulk = async (ids: string[], action: string, extra: Record<string, unknown> = {}) => {
    const result = await filesApi.bulk(org, { ids, action, ...extra });
    if (result.status === 200) {
      setAnnouncement(t(m.bulkDone, { count: result.body.updated }));
      setSelected(new Set());
      await load(true);
    }
    return result.status === 200;
  };

  const opened = rows.find((row) => row.id === openId) ?? null;

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length) startUploads(event.dataTransfer.files);
  };

  const empty =
    folder === "inbox" ? (
      <EmptyState
        title={t(m.emptyTitle)}
        body={t(m.emptyBody)}
        headingLevel={2}
        actions={[
          <Button key="upload" variant="primary" onClick={() => fileInput.current?.click()}>
            {t(m.upload)}
          </Button>,
        ]}
      />
    ) : (
      <EmptyState title={t(m.tabArchived)} body={t(m.emptyArchived)} headingLevel={2} />
    );

  return (
    <div
      data-testid="documents-inbox"
      className="relative flex flex-col gap-4"
      onDragEnter={(event) => {
        if (event.dataTransfer.types.includes("Files")) setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => {
        if (event.currentTarget === event.target) setDragging(false);
      }}
      onDrop={onDrop}
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{t(m.title)}</h1>
          <p className="mt-1 max-w-2xl text-sm text-fg-muted">{t(m.intro)}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button
            variant="primary"
            onClick={() => fileInput.current?.click()}
            aria-keyshortcuts="U"
          >
            {t(m.upload)}
          </Button>
          <span className="text-xs text-fg-muted">{t(m.dropHint)}</span>
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            data-testid="file-input"
            aria-label={t(m.upload)}
            accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.heic,.heif,.xlsx,.docx,.csv,.ofx,.qfx,.qbo"
            onChange={(event) => {
              if (event.target.files?.length) startUploads(event.target.files);
              event.target.value = "";
            }}
          />
        </div>
      </header>

      <AddressCard org={org} />
      <UploadList uploads={uploads} />

      <div role="tablist" aria-label={t(m.folders)} className="flex gap-4 border-b border-border">
        {(["inbox", "archived"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={folder === value}
            className={
              folder === value
                ? "border-b-2 border-border-accent pb-2 text-sm font-semibold text-fg"
                : "pb-2 text-sm text-fg-muted hover:text-fg"
            }
            onClick={() => setFolder(value)}
          >
            {value === "inbox" ? t(m.tabInbox) : t(m.tabArchived)}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-4 lg:flex-row">
        <div className="min-w-0 flex-1">
          <DataGrid
            data={shown}
            columns={columns}
            getRowId={(row) => row.id}
            getRowLabel={(row) => row.name}
            labels={labels}
            selectable
            selectedIds={selected}
            onSelectionChange={setSelected}
            onRowOpen={(row) => setOpenId(row.id)}
            status={status}
            height={560}
            toolbar={
              tags.length > 0 ? (
                <label className="flex items-center gap-2 text-sm">
                  <span>{t(m.tagFilter)}</span>
                  <select
                    className="min-h-touch-target rounded-md border border-border-strong bg-surface px-2"
                    value={tag}
                    onChange={(event) => setTag(event.target.value)}
                  >
                    <option value="">{t(m.anyTag)}</option>
                    {tags.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null
            }
            bulkActions={(chosen) => (
              <>
                {folder === "inbox" ? (
                  <Button
                    size="sm"
                    onClick={() =>
                      void bulk(
                        chosen.map((r) => r.id),
                        "archive",
                      )
                    }
                  >
                    {t(m.bulkArchive)}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={() =>
                      void bulk(
                        chosen.map((r) => r.id),
                        "unarchive",
                      )
                    }
                  >
                    {t(m.bulkUnarchive)}
                  </Button>
                )}
                <Button size="sm" onClick={() => setTagging(chosen.map((r) => r.id))}>
                  {t(m.bulkTag)}
                </Button>
              </>
            )}
            emptyState={empty}
            noResultsState={<EmptyState title={t(m.noResults)} headingLevel={2} compact />}
            errorState={
              <ErrorState
                title={t(m.loadFailed)}
                retryLabel={t(m.retry)}
                onRetry={() => void load()}
              />
            }
          />
        </div>
        {opened ? (
          <Previewer
            key={opened.id}
            org={org}
            document={opened}
            locale={locale}
            onClose={() => setOpenId(null)}
            onSaved={() => void load(true)}
          />
        ) : null}
      </div>

      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>

      {tagging ? (
        <BulkTagDialog
          count={tagging.length}
          onCancel={() => setTagging(null)}
          onApply={async (tagsToAdd, period, taxYear) => {
            const ids = tagging;
            let ok = true;
            if (tagsToAdd.length) ok = (await bulk(ids, "add_tags", { tags: tagsToAdd })) && ok;
            if (period) ok = (await bulk(ids, "set_period", { period })) && ok;
            if (taxYear)
              ok = (await bulk(ids, "set_tax_year", { tax_year: Number(taxYear) })) && ok;
            if (ok) setTagging(null);
            return ok;
          }}
        />
      ) : null}

      {dragging ? (
        <div
          data-testid="drop-overlay"
          className="pointer-events-none fixed inset-0 z-50 flex flex-col items-center justify-center gap-2 bg-surface-inverse/80 text-fg-inverse"
        >
          <p className="text-2xl font-semibold">{t(m.dropHere)}</p>
          <p className="text-sm">{t(m.dropHint)}</p>
        </div>
      ) : null}
    </div>
  );
}

// ---- inbox address ----------------------------------------------------------------------------

function AddressCard({ org }: { org: string }) {
  const t = useFormatMessage();
  const [address, setAddress] = useState<InboundAddress | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    let live = true;
    void filesApi.inboundAddress(org).then((result) => {
      if (live && result.status === 200 && result.body.address) setAddress(result.body);
    });
    return () => {
      live = false;
    };
  }, [org]);
  if (!address) return null; // no permission to see it, or not reachable: nothing to copy
  return (
    <section
      aria-label={t(m.addressTitle)}
      className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface-subtle p-3"
    >
      <span className="text-sm font-semibold">{t(m.addressTitle)}</span>
      <code data-testid="inbound-address" className="rounded bg-surface px-2 py-1 text-sm">
        {address.address}
      </code>
      <Button
        size="sm"
        onClick={() => {
          void navigator.clipboard?.writeText(address.address).then(() => setCopied(true));
        }}
      >
        {t(m.addressCopy)}
      </Button>
      <span role="status" className="text-xs text-fg-success">
        {copied ? t(m.addressCopied) : ""}
      </span>
      <span className="w-full text-xs text-fg-muted">{t(m.addressHelp)}</span>
    </section>
  );
}

// ---- uploads ----------------------------------------------------------------------------------

function UploadList({ uploads }: { uploads: UploadRow[] }) {
  const t = useFormatMessage();
  if (!uploads.length) return null;
  const text = (upload: UploadRow): string => {
    const { state } = upload;
    switch (state.kind) {
      case "refused":
        return state.reason === "size"
          ? t(m.uploadTooLarge, { name: upload.name, size: humanSize(upload.size) })
          : t(m.uploadType, { name: upload.name });
      case "uploading":
        return t(m.uploadProgress, { percent: state.percent });
      case "checking":
        return t(m.uploadChecking);
      case "done":
        return state.duplicate ? t(m.uploadDuplicate) : t(m.uploadDone);
      case "failed":
        return state.message || t(m.uploadFailed);
    }
  };
  return (
    <section aria-label={t(m.uploadsTitle)} className="rounded-lg border border-border p-3">
      <h2 className="mb-2 text-sm font-semibold">{t(m.uploadsTitle)}</h2>
      <ul className="flex flex-col gap-2">
        {uploads.map((upload) => (
          <li key={upload.id} data-testid="upload-row" className="flex flex-col gap-1 text-sm">
            <span className="flex justify-between gap-2">
              <span className="truncate font-medium">{upload.name}</span>
              <span
                className={
                  upload.state.kind === "failed" || upload.state.kind === "refused"
                    ? "text-fg-danger"
                    : "text-fg-muted"
                }
              >
                {text(upload)}
              </span>
            </span>
            {upload.state.kind === "uploading" ? (
              <progress
                className="h-1 w-full"
                max={100}
                value={upload.state.percent}
                aria-label={t(m.uploadProgress, { percent: upload.state.percent })}
              />
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---- previewer ----------------------------------------------------------------------------------

function Previewer({
  org,
  document,
  locale,
  onClose,
  onSaved,
}: {
  org: string;
  document: FileDocument;
  locale: AppLocale;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = useFormatMessage();
  const [preview, setPreview] = useState<string | null>(null);
  const [period, setPeriod] = useState(document.period);
  const [taxYear, setTaxYear] = useState(
    document.tax_year === null ? "" : String(document.tax_year),
  );
  const [tags, setTags] = useState(document.tags.join(", "));
  const [saveState, setSaveState] = useState<"" | "saved" | "failed">("");
  const ids = useId();

  useEffect(() => {
    if (document.status !== "clean" || document.preview_status !== "ready") return;
    let live = true;
    void filesApi.signedUrl(org, document.id, "preview").then((result) => {
      if (live && result.status === 200) setPreview(result.body.url);
    });
    return () => {
      live = false;
    };
  }, [org, document.id, document.status, document.preview_status]);

  const message = (() => {
    if (document.status === "infected")
      return t(m.previewInfected, { signature: "" }).replace(" ()", "");
    if (document.status !== "clean") return t(m.previewScanning);
    if (document.preview_status === "pending") return t(m.previewPending);
    if (document.preview_status === "password") return t(m.previewPassword);
    if (document.preview_status !== "ready") return t(m.previewNone);
    return "";
  })();

  const download = async () => {
    const result = await filesApi.signedUrl(org, document.id, "file", true);
    if (result.status === 200) window.location.assign(result.body.url);
  };

  const save = async () => {
    const result = await filesApi.update(org, document.id, {
      period,
      tax_year: taxYear ? Number(taxYear) : null,
      tags: tags
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
    });
    setSaveState(result.status === 200 ? "saved" : "failed");
    if (result.status === 200) onSaved();
  };

  return (
    <aside
      aria-label={t(m.previewTitle)}
      data-testid="previewer"
      className="flex w-full flex-col gap-3 rounded-lg border border-border p-4 lg:w-96"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className="break-all text-base font-semibold">{document.name}</h2>
        <Button size="sm" variant="ghost" onClick={onClose}>
          {t(m.close)}
        </Button>
      </div>
      <StatusBadge status={STATUS_KEY[document.status]} label={statusLabel(t, document.status)} />
      {preview ? (
        // A short-lived signed bucket URL: nothing for next/image to optimise or cache, so the
        // preview is drawn as a background with an image role and its text alternative.
        <div
          role="img"
          aria-label={t(m.previewAlt, { name: document.name })}
          data-testid="preview-image"
          className="h-96 w-full rounded border border-border bg-contain bg-center bg-no-repeat"
          style={{ backgroundImage: `url("${preview}")` }}
        />
      ) : message ? (
        <p className="rounded bg-surface-subtle p-3 text-sm text-fg-muted">{message}</p>
      ) : null}
      <dl className="grid grid-cols-[6rem_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-fg-muted">{t(m.detailFrom)}</dt>
        <dd className="break-all">
          {document.source === "email" ? document.sender : document.uploaded_by}
          {document.source === "email" && !document.sender_known ? (
            <Badge tone="warning" className="ml-2">
              {t(m.unknownSender)}
            </Badge>
          ) : null}
        </dd>
        <dt className="text-fg-muted">{t(m.detailSize)}</dt>
        <dd>{humanSize(document.size)}</dd>
        <dt className="text-fg-muted">{t(m.detailAdded)}</dt>
        <dd>{formatDate(new Date(document.created_at), { locale })}</dd>
      </dl>
      {document.status === "clean" ? (
        <Button size="sm" onClick={() => void download()}>
          {t(m.download)}
        </Button>
      ) : null}
      <div className="flex flex-col gap-2">
        <label htmlFor={`${ids}-period`} className="text-sm font-medium">
          {t(m.fieldPeriod)}
        </label>
        <Input id={`${ids}-period`} value={period} onChange={(e) => setPeriod(e.target.value)} />
        <label htmlFor={`${ids}-year`} className="text-sm font-medium">
          {t(m.fieldTaxYear)}
        </label>
        <Input
          id={`${ids}-year`}
          inputMode="numeric"
          value={taxYear}
          onChange={(e) => setTaxYear(e.target.value)}
        />
        <label htmlFor={`${ids}-tags`} className="text-sm font-medium">
          {t(m.fieldTags)}
        </label>
        <Input id={`${ids}-tags`} value={tags} onChange={(e) => setTags(e.target.value)} />
        <div className="flex items-center gap-2">
          <Button size="sm" variant="primary" onClick={() => void save()}>
            {t(m.save)}
          </Button>
          <span
            role="status"
            className={
              saveState === "failed" ? "text-sm text-fg-danger" : "text-sm text-fg-success"
            }
          >
            {saveState === "saved" ? t(m.saved) : saveState === "failed" ? t(m.saveFailed) : ""}
          </span>
        </div>
      </div>
      <CreateFromFile org={org} documentId={document.id} />
    </aside>
  );
}

// ---- bulk tag dialog ----------------------------------------------------------------------------

function BulkTagDialog({
  count,
  onCancel,
  onApply,
}: {
  count: number;
  onCancel: () => void;
  onApply: (tags: string[], period: string, taxYear: string) => Promise<boolean>;
}) {
  const t = useFormatMessage();
  const ids = useId();
  const [tags, setTags] = useState("");
  const [period, setPeriod] = useState("");
  const [taxYear, setTaxYear] = useState("");
  const [failed, setFailed] = useState(false);
  return (
    <Dialog
      open
      onOpenChange={(open) => (open ? undefined : onCancel())}
      title={t(m.bulkTagTitle, { count })}
      closeLabel={t(m.close)}
      footer={
        <>
          <Button onClick={onCancel}>{t(m.cancel)}</Button>
          <Button
            variant="primary"
            onClick={() =>
              void onApply(
                tags
                  .split(",")
                  .map((value) => value.trim())
                  .filter(Boolean),
                period.trim(),
                taxYear.trim(),
              ).then((ok) => setFailed(!ok))
            }
          >
            {t(m.apply)}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-2">
        <label htmlFor={`${ids}-tags`} className="text-sm font-medium">
          {t(m.fieldTags)}
        </label>
        <Input id={`${ids}-tags`} value={tags} onChange={(e) => setTags(e.target.value)} />
        <label htmlFor={`${ids}-period`} className="text-sm font-medium">
          {t(m.fieldPeriod)}
        </label>
        <Input id={`${ids}-period`} value={period} onChange={(e) => setPeriod(e.target.value)} />
        <label htmlFor={`${ids}-year`} className="text-sm font-medium">
          {t(m.fieldTaxYear)}
        </label>
        <Input
          id={`${ids}-year`}
          inputMode="numeric"
          value={taxYear}
          onChange={(e) => setTaxYear(e.target.value)}
        />
        {failed ? <p className="text-sm text-fg-danger">{t(m.saveFailed)}</p> : null}
      </div>
    </Dialog>
  );
}
