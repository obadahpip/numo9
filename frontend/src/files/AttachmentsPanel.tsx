"use client";

import { Button, StatusBadge } from "@numo9/ui";
import { useCallback, useEffect, useRef, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { filesApi, humanSize, type Attachment } from "./api";
import { fm as m } from "./messages";
import { uploadFile, type UploadState } from "./upload";

export interface AttachmentsPanelProps {
  org: string;
  /** The record, as the API names it: model label + public id (`contacts.Contact`, `<uuid>`). */
  recordType: string;
  recordId: string;
  /** Read-only when the person can't change the record (no attach / remove buttons). */
  canEdit?: boolean;
}

interface Pending {
  id: string;
  name: string;
  state: UploadState;
}

/**
 * Attachments panel for any record's detail page (A-06-T13): the record's documents (newest
 * first) with their scan status, download, remove, and "Attach files" — an upload that lands in
 * the documents store and is linked to this record (A-06-T09 attachments API). Drop files on the
 * panel to attach them. Reused by every detail page: contacts first (B-01), then invoices, bills
 * and assets.
 */
export function AttachmentsPanel({
  org,
  recordType,
  recordId,
  canEdit = true,
}: AttachmentsPanelProps) {
  const t = useFormatMessage();
  const input = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<Attachment[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [pending, setPending] = useState<Pending[]>([]);
  const [announcement, setAnnouncement] = useState("");

  const load = useCallback(async () => {
    const result = await filesApi.attachments(org, recordType, recordId);
    if (result.status === 200 && Array.isArray(result.body.results)) {
      setItems(result.body.results);
      setStatus("ready");
    } else {
      setStatus("error");
    }
  }, [org, recordType, recordId]);

  useEffect(() => {
    void load();
  }, [load]);

  const scanning = items.some(
    (a) => a.document.status === "scanning" || a.document.status === "uploading",
  );
  useEffect(() => {
    if (!scanning) return;
    const timer = setInterval(() => void load(), 3000);
    return () => clearInterval(timer);
  }, [scanning, load]);

  const attachFiles = (files: FileList | File[]) => {
    for (const [index, file] of Array.from(files).entries()) {
      const id = `${Date.now()}-${index}-${file.name}`;
      setPending((current) => [
        ...current,
        { id, name: file.name, state: { kind: "uploading", percent: 0 } },
      ]);
      const update = (state: UploadState) =>
        setPending((current) => current.map((p) => (p.id === id ? { ...p, state } : p)));
      void uploadFile(org, file, update).then(async (state) => {
        if (state.kind !== "done") return;
        const linked = await filesApi.attach(org, state.document.id, recordType, recordId);
        if (linked.status === 200 || linked.status === 201) {
          setPending((current) => current.filter((p) => p.id !== id));
          setAnnouncement(t(m.attachDone, { name: file.name }));
          await load();
        } else {
          update({ kind: "failed", message: t(m.attachFailed) });
        }
      });
    }
  };

  const remove = async (attachment: Attachment) => {
    const result = await filesApi.detach(org, attachment.id);
    if (result.status === 204 || result.status === 200) {
      setItems((current) => current.filter((a) => a.id !== attachment.id));
      setAnnouncement(t(m.attachRemoved, { name: attachment.document.name }));
    } else {
      setAnnouncement(t(m.attachFailed));
    }
  };

  const download = async (attachment: Attachment) => {
    const result = await filesApi.signedUrl(org, attachment.document.id, "file", true);
    if (result.status === 200) window.location.assign(result.body.url);
  };

  return (
    <section
      aria-labelledby={`${recordId}-attachments`}
      data-testid="attachments-panel"
      className="flex flex-col gap-3 rounded-lg border border-border p-4"
      onDragOver={(event) => {
        if (canEdit) event.preventDefault();
      }}
      onDrop={(event) => {
        if (!canEdit) return;
        event.preventDefault();
        if (event.dataTransfer.files.length) attachFiles(event.dataTransfer.files);
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 id={`${recordId}-attachments`} className="text-base font-semibold">
          {t(m.attachTitle)}
          {status === "ready" ? (
            <span className="ms-2 text-sm font-normal text-fg-muted">
              {t(m.attachCount, { count: items.length })}
            </span>
          ) : null}
        </h2>
        {canEdit ? (
          <>
            <Button size="sm" onClick={() => input.current?.click()}>
              {t(m.attachAdd)}
            </Button>
            <input
              ref={input}
              type="file"
              multiple
              hidden
              data-testid="attach-input"
              aria-label={t(m.attachAdd)}
              onChange={(event) => {
                if (event.target.files?.length) attachFiles(event.target.files);
                event.target.value = "";
              }}
            />
          </>
        ) : null}
      </div>

      {status === "loading" ? <p className="text-sm text-fg-muted">{t(m.loading)}</p> : null}
      {status === "error" ? (
        <p className="flex items-center gap-2 text-sm text-fg-danger">
          {t(m.attachLoadFailed)}
          <Button size="sm" variant="ghost" onClick={() => void load()}>
            {t(m.retry)}
          </Button>
        </p>
      ) : null}
      {status === "ready" && items.length === 0 && pending.length === 0 ? (
        <p className="text-sm text-fg-muted">
          {canEdit ? t(m.attachEmpty) : t(m.attachEmptyReadOnly)}
        </p>
      ) : null}

      {items.length || pending.length ? (
        <ul className="flex flex-col divide-y divide-border">
          {items.map((attachment) => (
            <li
              key={attachment.id}
              data-testid="attachment"
              className="flex flex-wrap items-center gap-2 py-2 text-sm"
            >
              <span className="min-w-0 flex-1 truncate font-medium">
                {attachment.document.name}
              </span>
              <span className="text-fg-muted">{humanSize(attachment.document.size)}</span>
              {attachment.document.status !== "clean" ? (
                <StatusBadge
                  status={attachment.document.status === "infected" ? "infected" : "scanning"}
                  label={
                    attachment.document.status === "infected"
                      ? t(m.statusInfected)
                      : t(m.statusScanning)
                  }
                />
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => void download(attachment)}
                  aria-label={t(m.attachDownload, { name: attachment.document.name })}
                >
                  {t(m.download)}
                </Button>
              )}
              {canEdit ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => void remove(attachment)}
                  aria-label={t(m.attachRemove, { name: attachment.document.name })}
                >
                  {t(m.attachRemoveShort)}
                </Button>
              ) : null}
            </li>
          ))}
          {pending.map((item) => (
            <li
              key={item.id}
              data-testid="attachment-pending"
              className="flex items-center gap-2 py-2 text-sm"
            >
              <span className="min-w-0 flex-1 truncate">{item.name}</span>
              <span
                className={
                  item.state.kind === "failed" || item.state.kind === "refused"
                    ? "text-fg-danger"
                    : "text-fg-muted"
                }
              >
                {item.state.kind === "uploading"
                  ? t(m.uploadProgress, { percent: item.state.percent })
                  : item.state.kind === "checking" || item.state.kind === "done"
                    ? t(m.uploadChecking)
                    : item.state.kind === "refused"
                      ? item.state.reason === "size"
                        ? t(m.uploadTooLarge, { name: item.name, size: "25 MB" })
                        : t(m.uploadType, { name: item.name })
                      : item.state.message || t(m.uploadFailed)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </section>
  );
}
