import type { AgingBarLabels, AgingBucket, OverviewCardLabels, OverviewTile } from "./OverviewPage";

/** Sample data for the overview stories and tests (an Ontario wholesaler, CAD). */
export const salesTiles: OverviewTile[] = [
  { key: "draft", label: "Draft", count: 4, amount: "3120.00", href: "#draft" },
  {
    key: "awaiting_approval",
    label: "Awaiting approval",
    count: 2,
    amount: "1850.50",
    href: "#awaiting_approval",
  },
  {
    key: "awaiting_payment",
    label: "Awaiting payment",
    count: 11,
    amount: "18400.00",
    href: "#awaiting_payment",
  },
  {
    key: "overdue",
    label: "Overdue",
    count: 3,
    amount: "4275.25",
    href: "#overdue",
    tone: "attention",
  },
];

export const emptyTiles: OverviewTile[] = salesTiles.map((tile) => ({
  ...tile,
  count: 0,
  amount: "0.00",
}));

export const agingBuckets: AgingBucket[] = [
  { key: "current", label: "Current", amount: "14124.75", href: "#current" },
  { key: "1_30", label: "1–30 days", amount: "2400.00", href: "#1_30" },
  { key: "31_60", label: "31–60 days", amount: "1250.25", href: "#31_60" },
  { key: "61_90", label: "61–90 days", amount: "0.00" },
  { key: "over_90", label: "Over 90 days", amount: "625.00", href: "#over_90" },
];

export const tileLabel = (tile: OverviewTile, count: string, amount: string) =>
  `${tile.label}: ${count} invoices, ${amount}`;

export const cardLabels: OverviewCardLabels = {
  loading: "Loading…",
  retry: "Try again",
  reference: (reference) => `Reference: ${reference}`,
};

export const agingLabels: AgingBarLabels = {
  chart: (total) => `Money coming in by age: ${total} owed`,
  empty: "Nothing owed — every invoice is paid.",
};
