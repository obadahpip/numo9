"use client";

/**
 * Layout editor panel (K-01-T15, wireframe 57): a right-hand panel beside the report, not a
 * separate page. Rows — drag to reorder (or the arrow buttons, for the keyboard), rename (the
 * chart keeps the account name; the layout keeps the label), hide; text blocks between rows;
 * footnotes; a note on one cell (kept when the report runs again, K-01-T09). Save as draft ·
 * Publish (an immutable snapshot) · Save as custom. A published layout is never edited: saving
 * starts the next version (K-01-T08).
 */
import { Button, Checkbox, Input, Select } from "@numo9/ui";
import { useMemo, useState, type DragEvent } from "react";

import { useFormatMessage } from "@/i18n";

import { reportsApi, type LayoutConfig, type ReportBody, type ReportSummary } from "./api";
import { layoutMessages as m } from "./messages";
import type { RunParams } from "./ReportRunner";

function GripIcon() {
  return (
    <svg viewBox="0 0 12 16" className="h-4 w-3" aria-hidden="true">
      {[3, 8, 13].map((y) => (
        <g key={y} fill="currentColor">
          <circle cx="3" cy={y} r="1.3" />
          <circle cx="9" cy={y} r="1.3" />
        </g>
      ))}
    </svg>
  );
}

function ArrowIcon({ up = false }: { up?: boolean }) {
  return (
    <svg viewBox="0 0 16 16" className={up ? "size-4" : "size-4 rotate-180"} aria-hidden="true">
      <path d="M8 13V3M4 7l4-4 4 4" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

export interface EditorRow {
  key: string;
  original: string;
  label: string;
  hidden: boolean;
}

export interface TextBlock {
  after: string;
  text: string;
}

/** The editable rows of a run, in the order of the layout (text blocks aside). */
export function editorRows(body: ReportBody): EditorRow[] {
  const config = body.layout?.config ?? {};
  const settings = new Map((config.rows ?? []).map((r) => [r.key, r]));
  const rows = body.rows.filter((r) => r.kind !== "text");
  const shown = rows.map((r) => ({
    key: r.key,
    original: r.label,
    label: settings.get(r.key)?.label ?? "",
    hidden: false,
  }));
  // Hidden rows aren't in the run: bring them back from the layout so they can be shown again.
  for (const [key, setting] of settings) {
    if (setting.hidden && !shown.some((r) => r.key === key)) {
      shown.push({ key, original: setting.label || key, label: setting.label ?? "", hidden: true });
    }
  }
  return shown;
}

export function layoutConfig(rows: EditorRow[], blocks: TextBlock[]): LayoutConfig {
  return {
    rows: rows.map((row) => ({
      key: row.key,
      ...(row.label && row.label !== row.original ? { label: row.label } : {}),
      ...(row.hidden ? { hidden: true } : {}),
    })),
    text_blocks: blocks.filter((b) => b.text.trim()).map((b) => ({ after: b.after, text: b.text })),
  };
}

export function move<T>(items: T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) return items;
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item as T);
  return next;
}

export interface LayoutEditorProps {
  org: string;
  report: ReportSummary;
  body: ReportBody;
  params: RunParams;
  onClose: () => void;
  /** Run again with the saved layout. */
  onSaved: (layout: string) => void;
}

export function LayoutEditor({ org, report, body, onClose, onSaved }: LayoutEditorProps) {
  const fm = useFormatMessage();
  const current = body.layout;
  const [name, setName] = useState(current?.name ?? fm(m.defaultName, { report: report.name }));
  const [rows, setRows] = useState<EditorRow[]>(() => editorRows(body));
  const [blocks, setBlocks] = useState<TextBlock[]>(() =>
    (current?.config.text_blocks ?? []).map((b) => ({ after: b.after ?? "", text: b.text })),
  );
  const [notes, setNotes] = useState(current?.notes ?? body.notes ?? "");
  const [dragging, setDragging] = useState<number | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [noteRow, setNoteRow] = useState(rows[0]?.key ?? "");
  const [noteColumn, setNoteColumn] = useState("");
  const [noteText, setNoteText] = useState("");

  // The run's cleaned parameters (a preset already resolved to its dates): what the layout runs
  // with, and what publishing freezes.
  const runParams = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(body.params)
          .filter(([, v]) => v !== null && v !== "")
          .map(([k, v]) => [k, String(v)]),
      ),
    [body.params],
  );

  const drop = (index: number) => (event: DragEvent) => {
    event.preventDefault();
    if (dragging !== null) setRows((r) => move(r, dragging, index));
    setDragging(null);
  };

  const save = async (kind: "draft" | "custom" | "publish") => {
    setBusy(true);
    setStatus("");
    const saved = await reportsApi.saveLayout(org, report.slug, {
      name: name.trim(),
      status: kind === "custom" ? "custom" : "draft",
      params: runParams,
      config: layoutConfig(rows, blocks),
      notes,
    });
    if (saved.status !== 201) {
      setBusy(false);
      setStatus(fm(m.failed, { detail: saved.body?.detail ?? String(saved.status) }));
      return;
    }
    let layout = saved.body;
    if (kind === "publish") {
      const published = await reportsApi.publish(org, layout.id);
      if (published.status !== 200) {
        setBusy(false);
        setStatus(fm(m.failed, { detail: published.body?.detail ?? String(published.status) }));
        return;
      }
      layout = published.body;
    }
    setBusy(false);
    setStatus(
      kind === "publish"
        ? fm(m.publishedNow, { version: layout.version })
        : kind === "custom"
          ? fm(m.savedCustom)
          : fm(m.saved),
    );
    onSaved(layout.id);
  };

  const saveNote = async () => {
    const result = await reportsApi.setNote(org, report.slug, {
      row: noteRow,
      column: noteColumn,
      text: noteText,
      ...(current ? { layout: current.id } : {}),
    });
    if (result.status === 200) {
      setStatus(fm(m.noteSaved));
      onSaved(current?.id ?? "");
    } else setStatus(fm(m.failed, { detail: result.body?.detail ?? String(result.status) }));
  };

  const labelOf = (row: EditorRow) => row.label || row.original;

  return (
    <aside
      aria-labelledby="layout-editor-title"
      className="fixed inset-y-0 end-0 z-40 flex w-full max-w-md flex-col gap-4 overflow-y-auto border-s border-border bg-surface p-4 shadow-elevation-3"
      data-layout-editor=""
    >
      <div className="flex items-center justify-between gap-2">
        <h2 id="layout-editor-title" className="text-lg font-bold text-fg">
          {fm(m.title)}
        </h2>
        <Button variant="ghost" size="sm" onClick={onClose}>
          {fm(m.close)}
        </Button>
      </div>
      {current?.status === "published" ? (
        <p className="rounded-md bg-surface-info-subtle p-3 text-sm text-fg" role="note">
          {fm(m.published, { version: current.version, next: current.version + 1 })}
        </p>
      ) : null}
      <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
        {fm(m.name)}
        <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
      </label>

      <section className="flex flex-col gap-2" aria-labelledby="layout-rows">
        <h3 id="layout-rows" className="text-sm font-bold text-fg">
          {fm(m.rows)}
        </h3>
        <p className="text-xs text-fg-muted">{fm(m.rowsHint)}</p>
        <ol className="flex flex-col gap-2" aria-labelledby="layout-rows">
          {rows.map((row, index) => (
            <li
              key={row.key}
              draggable
              onDragStart={() => setDragging(index)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={drop(index)}
              className="flex flex-col gap-1 rounded-md border border-border p-2"
              data-layout-row={row.key}
            >
              <div className="flex items-center gap-1">
                <span
                  className="cursor-grab select-none px-1 text-fg-muted"
                  aria-label={fm(m.drag, { row: labelOf(row) })}
                  role="img"
                >
                  <GripIcon />
                </span>
                <Input
                  aria-label={fm(m.rename, { row: row.original })}
                  value={row.label}
                  placeholder={row.original}
                  onChange={(e) =>
                    setRows((r) =>
                      r.map((x, i) => (i === index ? { ...x, label: e.target.value } : x)),
                    )
                  }
                />
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={fm(m.moveUp, { row: labelOf(row) })}
                  disabled={index === 0}
                  onClick={() => setRows((r) => move(r, index, index - 1))}
                >
                  <ArrowIcon up />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={fm(m.moveDown, { row: labelOf(row) })}
                  disabled={index === rows.length - 1}
                  onClick={() => setRows((r) => move(r, index, index + 1))}
                >
                  <ArrowIcon />
                </Button>
              </div>
              <div className="flex items-center justify-between gap-2">
                <Checkbox
                  checked={row.hidden}
                  onCheckedChange={(on) =>
                    setRows((r) =>
                      r.map((x, i) => (i === index ? { ...x, hidden: on === true } : x)),
                    )
                  }
                  label={fm(m.hide, { row: labelOf(row) })}
                />
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setBlocks((b) => [...b, { after: row.key, text: "" }])}
                >
                  {fm(m.addText, { row: labelOf(row) })}
                </Button>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="flex flex-col gap-2" aria-labelledby="layout-text">
        <div className="flex items-center justify-between gap-2">
          <h3 id="layout-text" className="text-sm font-bold text-fg">
            {fm(m.textBlocks)}
          </h3>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setBlocks((b) => [...b, { after: "", text: "" }])}
          >
            {fm(m.addTextTop)}
          </Button>
        </div>
        {blocks.map((block, index) => {
          const after = rows.find((r) => r.key === block.after);
          const label = after ? fm(m.textAfter, { row: labelOf(after) }) : fm(m.textTop);
          return (
            <div key={`${block.after}-${index}`} className="flex flex-col gap-1">
              <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
                {label}
                <textarea
                  className="min-h-16 rounded-md border border-border-strong bg-surface p-2 text-sm text-fg"
                  value={block.text}
                  onChange={(e) =>
                    setBlocks((b) =>
                      b.map((x, i) => (i === index ? { ...x, text: e.target.value } : x)),
                    )
                  }
                />
              </label>
              <Button
                size="sm"
                variant="ghost"
                className="self-end"
                onClick={() => setBlocks((b) => b.filter((_, i) => i !== index))}
              >
                {fm(m.removeText)}
              </Button>
            </div>
          );
        })}
      </section>

      <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
        {fm(m.footnotes)}
        <textarea
          className="min-h-16 rounded-md border border-border-strong bg-surface p-2 text-sm font-normal text-fg"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>

      <section
        className="flex flex-col gap-2 rounded-md border border-border p-3"
        aria-labelledby="layout-note"
      >
        <h3 id="layout-note" className="text-sm font-bold text-fg">
          {fm(m.noteHeading)}
        </h3>
        <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
          {fm(m.noteRow)}
          <Select
            aria-label={fm(m.noteRow)}
            value={noteRow}
            onValueChange={setNoteRow}
            options={rows.map((r) => ({ value: r.key, label: labelOf(r) }))}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
          {fm(m.noteColumn)}
          <Select
            aria-label={fm(m.noteColumn)}
            value={noteColumn || "__row"}
            onValueChange={(v) => setNoteColumn(v === "__row" ? "" : v)}
            options={[
              { value: "__row", label: fm(m.noteWholeRow) },
              ...body.columns.map((c) => ({ value: c.key, label: c.label })),
            ]}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
          {fm(m.noteText)}
          <Input value={noteText} onChange={(e) => setNoteText(e.target.value)} />
        </label>
        <Button size="sm" onClick={() => void saveNote()} disabled={!noteRow}>
          {fm(m.saveNote)}
        </Button>
      </section>

      <div className="sticky bottom-0 flex flex-col gap-2 border-t border-border bg-surface pt-3">
        <p className="text-xs text-fg-muted">{fm(m.publishHint)}</p>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => void save("draft")} disabled={busy || !name.trim()}>
            {fm(m.saveDraft)}
          </Button>
          <Button
            variant="primary"
            onClick={() => void save("publish")}
            disabled={busy || !name.trim()}
          >
            {fm(m.publish)}
          </Button>
          <Button
            variant="ghost"
            onClick={() => void save("custom")}
            disabled={busy || !name.trim()}
          >
            {fm(m.saveCustom)}
          </Button>
        </div>
        <p role="status" className="text-sm text-fg">
          {status}
        </p>
      </div>
    </aside>
  );
}
