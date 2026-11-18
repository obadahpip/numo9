"use client";

import {
  ChevronDownIcon,
  DataGrid,
  type DataGridColumn,
  type DataGridLabels,
  type GridViewState,
} from "@numo9/ui";
import { useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import type { DirectoryGrouping, DirectoryRow } from "./api";
import { m } from "./messages";

const ROW_HEIGHT = 44;
const MAX_SECTION_HEIGHT = 480;

export interface GroupedDirectoryProps {
  grouping: DirectoryGrouping[];
  rows: DirectoryRow[];
  columns: DataGridColumn<DirectoryRow>[];
  labels: DataGridLabels;
  view: GridViewState;
  onViewChange: (view: GridViewState) => void;
  onRowOpen: (row: DirectoryRow) => void;
  onRowOpenNewTab: (row: DirectoryRow) => void;
}

/**
 * Directory grouped by practice group (V-02-T08): one section per group in tree order (indented
 * by level), then "No group". Each header names the group and how many matching organisations
 * are filed in it — the server's `grouping` counts — and toggles its section; empty groups are
 * left out. An organisation filed in two groups appears in both.
 */
export function GroupedDirectory({
  grouping,
  rows,
  columns,
  labels,
  view,
  onViewChange,
  onRowOpen,
  onRowOpenNewTab,
}: GroupedDirectoryProps) {
  const byId = new Map(rows.map((row) => [row.id, row]));
  const sections = grouping.filter((item) => item.count > 0);
  return (
    <div className="flex flex-col gap-4" data-grouped-directory="">
      {sections.map((item) => (
        <GroupSection
          key={item.group?.id ?? "none"}
          item={item}
          rows={item.organisations
            .map((id) => byId.get(id))
            .filter((row): row is DirectoryRow => !!row)}
          columns={columns}
          labels={labels}
          view={view}
          onViewChange={onViewChange}
          onRowOpen={onRowOpen}
          onRowOpenNewTab={onRowOpenNewTab}
        />
      ))}
    </div>
  );
}

function GroupSection({
  item,
  rows,
  columns,
  labels,
  view,
  onViewChange,
  onRowOpen,
  onRowOpenNewTab,
}: Omit<GroupedDirectoryProps, "grouping"> & { item: DirectoryGrouping }) {
  const t = useFormatMessage();
  const [open, setOpen] = useState(true);
  const bodyId = useId();
  const name = item.group ? item.group.name : t(m.noGroup);
  const depth = item.group?.depth ?? 1;
  return (
    <section
      data-group-section={item.group?.id ?? "none"}
      data-count={item.count}
      style={depth > 1 ? { marginInlineStart: `${(depth - 1) * 1}rem` } : undefined}
    >
      <h2 className="mb-2">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={bodyId}
          aria-label={t(m.groupToggle, { name })}
          onClick={() => setOpen((value) => !value)}
          className="min-h-8 text-base font-bold text-fg underline-offset-2 hover:underline"
        >
          <span
            aria-hidden="true"
            className={`me-1 inline-flex size-4 align-middle transition-transform ${open ? "" : "-rotate-90"}`}
          >
            <ChevronDownIcon />
          </span>
          <span data-group-header="">{t(m.groupHeader, { name, count: item.count })}</span>
        </button>
      </h2>
      <div id={bodyId} hidden={!open}>
        {open ? (
          <DataGrid
            manual
            data={rows}
            columns={columns}
            getRowId={(row) => row.id}
            getRowLabel={(row) => row.name}
            labels={labels}
            view={view}
            onViewChange={onViewChange}
            onRowOpen={onRowOpen}
            onRowOpenNewTab={onRowOpenNewTab}
            totalCount={rows.length}
            unfilteredCount={rows.length}
            status="ready"
            height={Math.min(MAX_SECTION_HEIGHT, ROW_HEIGHT * (rows.length + 2) + 64)}
          />
        ) : null}
      </div>
    </section>
  );
}
