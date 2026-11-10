import type { ReactNode } from "react";

export type Density = "comfortable" | "compact";

/** Row heights from the tokens (size.row.comfortable / size.row.compact). */
export const ROW_HEIGHT: Record<Density, number> = { comfortable: 44, compact: 32 };

export interface DataGridColumn<T> {
  id: string;
  /** Column heading (i18n). */
  header: string;
  /** Value used for sorting, filtering and the default cell. */
  accessor: (row: T) => string | number | boolean | null | undefined;
  /** Custom cell content; default: the accessor value. */
  cell?: (row: T) => ReactNode;
  sortable?: boolean;
  /** Figures align to the end (amounts). */
  align?: "start" | "end";
  /** Width in px (default: share the rest). */
  width?: number;
  /** Can be hidden in the column chooser (default true). */
  hideable?: boolean;
  /** Filter chip in the filter bar: one of these values (exact match on the accessor). */
  filterOptions?: { value: string; label: string }[];
  /** Included in the search box (default true for text columns). */
  searchable?: boolean;
}

/** Everything a saved view stores (A-10-T10 saved views hook; V-01 persists it server-side). */
export interface GridViewState {
  sorting: { id: string; desc: boolean }[];
  search: string;
  filters: Record<string, string>;
  hiddenColumns: string[];
  density: Density;
}

export const EMPTY_VIEW: GridViewState = {
  sorting: [],
  search: "",
  filters: {},
  hiddenColumns: [],
  density: "comfortable",
};

export interface DataGridLabels {
  /** Accessible name of the grid, e.g. "Organisations". */
  grid: string;
  search: string;
  columns: string;
  density: string;
  comfortable: string;
  compact: string;
  /** Filter chip "any value" option, e.g. "All". */
  filterAll: string;
  /** Filter chip text, e.g. ("Province", "Ontario") → "Province: Ontario". */
  filterChip: (column: string, value: string) => string;
  clearFilters: string;
  selectAll: string;
  /** Row checkbox name, e.g. (row) → "Select Maple Leaf Supply Ltd.". */
  selectRow: (rowLabel: string) => string;
  /** Bulk bar count, e.g. (12) → "12 selected". */
  selectedCount: (count: number) => string;
  clearSelection: string;
  /** Live region after filtering, e.g. (143, 2000) → "143 of 2,000 organisations". */
  resultCount: (shown: number, total: number) => string;
  loading: string;
}
