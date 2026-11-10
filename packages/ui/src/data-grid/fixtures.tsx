import { StatusBadge, type StatusKey } from "../primitives/StatusBadge";
import { formatMoney } from "../format/format";
import type { DataGridColumn, DataGridLabels } from "./types";

/** Sample directory data for the grid stories, tests and the 10,000-row performance check. */
export interface SampleOrg {
  id: string;
  name: string;
  province: string;
  status: StatusKey;
  owner: string;
  balance: string;
}

export const gridLabels: DataGridLabels = {
  grid: "Organisations",
  search: "Search organisations",
  columns: "Columns",
  density: "Row density",
  comfortable: "Comfortable",
  compact: "Compact",
  filterAll: "All",
  filterChip: (column, value) => `${column}: ${value}`,
  clearFilters: "Clear filters",
  selectAll: "Select all organisations",
  selectRow: (name) => `Select ${name}`,
  selectedCount: (count) => `${count.toLocaleString("en-CA")} selected`,
  clearSelection: "Clear selection",
  resultCount: (shown, total) =>
    `${shown.toLocaleString("en-CA")} of ${total.toLocaleString("en-CA")} organisations`,
  loading: "Loading organisations…",
};

const PROVINCES = ["ON", "QC", "BC", "AB", "MB", "NS"];
const STATUSES: StatusKey[] = ["active", "trial", "grace", "read_only", "demo"];
const NAMES = [
  "Maple",
  "Cedar",
  "Harbour",
  "Prairie",
  "Northern",
  "Granite",
  "Coastal",
  "Birch",
  "Aurora",
  "Summit",
];
const KINDS = [
  "Bakery",
  "Dental",
  "Logistics",
  "Renovations",
  "Farms",
  "Studio",
  "Consulting",
  "Outfitters",
];
const OWNERS = ["Dana Lee", "Samir Haddad", "Émilie Tremblay", "Jordan Smith", "Priya Patel"];

export function sampleOrgs(count: number): SampleOrg[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `org-${i + 1}`,
    name: `${NAMES[i % NAMES.length]} ${KINDS[(i * 7) % KINDS.length]} ${i + 1} Ltd.`,
    province: PROVINCES[i % PROVINCES.length]!,
    status: STATUSES[i % STATUSES.length]!,
    owner: OWNERS[i % OWNERS.length]!,
    balance: (((i * 7919) % 2_000_000) / 100 - 3_000).toFixed(2),
  }));
}

const STATUS_LABEL: Partial<Record<StatusKey, string>> = {
  active: "Active",
  trial: "Trial",
  grace: "Grace period",
  read_only: "Read-only",
  demo: "Demo",
};

export const orgColumns: DataGridColumn<SampleOrg>[] = [
  { id: "name", header: "Organisation", accessor: (o) => o.name, sortable: true, hideable: false },
  {
    id: "province",
    header: "Province",
    accessor: (o) => o.province,
    sortable: true,
    width: 120,
    filterOptions: PROVINCES.map((p) => ({ value: p, label: p })),
  },
  {
    id: "status",
    header: "Status",
    accessor: (o) => o.status,
    cell: (o) => <StatusBadge status={o.status} label={STATUS_LABEL[o.status] ?? o.status} />,
    sortable: true,
    width: 150,
    searchable: false,
    filterOptions: STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] ?? s })),
  },
  { id: "owner", header: "Owner", accessor: (o) => o.owner, sortable: true },
  {
    id: "balance",
    header: "Receivables",
    accessor: (o) => Number(o.balance),
    cell: (o) => formatMoney(o.balance, { locale: "en-CA" }),
    sortable: true,
    align: "end",
    width: 150,
    searchable: false,
  },
];
