"use client";

import { HighlightedText, StatusBadge, type DataGridColumn } from "@numo9/ui";

import type { FormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import { formatBn, type DirectoryRow, type DirectoryStatus } from "./api";
import { m } from "./messages";

/** Every column the directory offers, in default order (ids = API column keys). */
export const ALL_COLUMNS = [
  "name",
  "bn",
  "province",
  "package",
  "status",
  "fye",
  "overdue",
  "unfiled",
  "gst_cycle",
  "payroll",
  "owner",
  "legal_name",
  "industry",
  "tags",
  "groups",
] as const;

/** Shown when nothing else is chosen (wireframe 03: Organisation, BN, Province, Package, Status,
 * FYE, Overdue). */
export const DEFAULT_COLUMNS: string[] = [
  "name",
  "bn",
  "province",
  "package",
  "status",
  "fye",
  "overdue",
];

/** The row actions column: always last, never hidden, not sent to the API. */
export const ACTIONS_COLUMN = "actions";

export function statusText(t: FormatMessage, row: DirectoryRow): string {
  const status: DirectoryStatus | undefined = row.status;
  if (status === "trial" && typeof row.trial_days_left === "number") {
    return t(m.statusTrialDays, { days: row.trial_days_left });
  }
  return t(
    {
      trial: m.statusTrial,
      paid: m.statusPaid,
      demo: m.statusDemo,
      read_only: m.statusReadOnly,
      archived: m.statusArchived,
    }[status ?? "paid"],
  );
}

/** "Dec 31" in the user's language. */
export function fyeText(locale: string, row: DirectoryRow): string {
  if (!row.fye_month) return "";
  const date = new Date(Date.UTC(2001, row.fye_month - 1, row.fye_day ?? 1));
  return new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", timeZone: "UTC" })
    .format(date)
    .replace(".", "");
}

export interface ColumnContext {
  t: FormatMessage;
  locale: string;
  /** The search text, for highlighting matches (V-01-T10). */
  query: string;
  /** Labels of filter values from the facets (GST/HST cycle, provinces…). */
  labels: (filter: string, value: string) => string;
}

export function directoryColumns({
  t,
  locale,
  query,
  labels,
}: ColumnContext): DataGridColumn<DirectoryRow>[] {
  const count = (value: number | undefined) =>
    value === undefined ? "" : new Intl.NumberFormat(locale).format(value);
  return [
    {
      id: "name",
      header: t(m.colName),
      accessor: (row) => row.name,
      cell: (row) => (
        <a
          href={orgModuleUrl(row.id, "home")}
          tabIndex={-1}
          className="font-semibold text-fg hover:underline"
        >
          <HighlightedText text={row.name} query={query} />
        </a>
      ),
      sortable: true,
      hideable: false,
    },
    {
      id: "bn",
      header: t(m.colBn),
      accessor: (row) => row.bn,
      cell: (row) => (
        <span className="tabular-nums">
          <HighlightedText text={formatBn(row.bn)} query={query} />
        </span>
      ),
      sortable: true,
      width: 120,
    },
    {
      id: "province",
      header: t(m.colProvince),
      accessor: (row) => row.province,
      sortable: true,
      width: 100,
    },
    {
      id: "package",
      header: t(m.colPackage),
      accessor: (row) => row.package_name || row.package,
      sortable: true,
      width: 150,
    },
    {
      id: "status",
      header: t(m.colStatus),
      accessor: (row) => row.status,
      cell: (row) =>
        row.status ? <StatusBadge status={row.status} label={statusText(t, row)} /> : null,
      sortable: true,
      width: 130,
    },
    {
      id: "fye",
      header: t(m.colFye),
      accessor: (row) => fyeText(locale, row),
      sortable: true,
      width: 90,
    },
    {
      id: "overdue",
      header: t(m.colOverdue),
      accessor: (row) => row.overdue_count,
      cell: (row) => count(row.overdue_count),
      sortable: true,
      align: "end",
      width: 100,
    },
    {
      id: "unfiled",
      header: t(m.colUnfiled),
      accessor: (row) => row.unfiled_count,
      cell: (row) => count(row.unfiled_count),
      sortable: true,
      align: "end",
      width: 100,
    },
    {
      id: "gst_cycle",
      header: t(m.colGstCycle),
      accessor: (row) => (row.gst_cycle ? labels("gst_cycle", row.gst_cycle) : ""),
      sortable: true,
      width: 130,
    },
    {
      id: "payroll",
      header: t(m.colPayroll),
      accessor: (row) =>
        row.payroll_enabled === undefined ? "" : t(row.payroll_enabled ? m.yes : m.no),
      sortable: true,
      width: 90,
    },
    {
      id: "owner",
      header: t(m.colOwner),
      accessor: (row) => row.owner_name,
      cell: (row) => <HighlightedText text={row.owner_name ?? ""} query={query} />,
      sortable: true,
      width: 180,
    },
    {
      id: "legal_name",
      header: t(m.colLegalName),
      accessor: (row) => row.legal_name,
      sortable: true,
      width: 220,
    },
    {
      id: "industry",
      header: t(m.colIndustry),
      accessor: (row) => row.industry,
      sortable: true,
      width: 150,
    },
    {
      id: "tags",
      header: t(m.colTags),
      accessor: (row) => (row.tags ?? []).join(", "),
      width: 160,
    },
    {
      id: "groups",
      header: t(m.colGroups),
      accessor: (row) => (row.groups ?? []).map((group) => group.name).join(", "),
      cell: (row) => (
        <ul className="flex flex-wrap gap-1" aria-label={t(m.colGroups)}>
          {(row.groups ?? []).map((group) => (
            <li
              key={group.id}
              data-group-badge={group.id}
              className="rounded-full border border-border bg-surface-subtle px-2 text-xs font-semibold text-fg"
            >
              {group.name}
            </li>
          ))}
        </ul>
      ),
      width: 200,
    },
    {
      id: ACTIONS_COLUMN,
      header: t(m.colActions),
      accessor: () => "",
      cell: (row) => (
        <a
          href={orgModuleUrl(row.id, "home")}
          target="_blank"
          rel="noopener noreferrer"
          tabIndex={-1}
          aria-label={t(m.openNewTabFor, { name: row.name })}
          className="text-sm font-semibold text-fg underline"
        >
          {t(m.openNewTab)}
        </a>
      ),
      hideable: false,
      width: 140,
    },
  ];
}
