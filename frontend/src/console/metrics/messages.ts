import { defineMessages } from "@/i18n";

/** Console metrics dashboard (U-06-T06). */
export const m = defineMessages({
  title: { id: "console.metrics.title", defaultMessage: "Metrics", description: "Heading" },
  crumb: {
    id: "console.metrics.crumb",
    defaultMessage: "Platform console · Metrics",
    description: "Breadcrumb",
  },
  demoNote: {
    id: "console.metrics.demoNote",
    defaultMessage: "Demo organisations are not counted.",
    description: "Under the heading",
  },
  mrr: { id: "console.metrics.mrr", defaultMessage: "MRR", description: "Tile: monthly revenue" },
  active: {
    id: "console.metrics.active",
    defaultMessage: "Active organisations",
    description: "Tile",
  },
  trials: { id: "console.metrics.trials", defaultMessage: "Trials", description: "Tile" },
  conversion: {
    id: "console.metrics.conversion",
    defaultMessage: "Conversion (30 days)",
    description: "Tile",
  },
  churn: { id: "console.metrics.churn", defaultMessage: "Churn (30 days)", description: "Tile" },
  conversionDetail: {
    id: "console.metrics.conversionDetail",
    defaultMessage: "{converted} of {ended} trials that ended",
    description: "Under the conversion tile",
  },
  churnDetail: {
    id: "console.metrics.churnDetail",
    defaultMessage: "{cancelled} of {base} cancelled",
    description: "Under the churn tile",
  },
  noRate: {
    id: "console.metrics.noRate",
    defaultMessage: "—",
    description: "A rate with nothing to divide by",
  },
  showList: {
    id: "console.metrics.showList",
    defaultMessage: "Show the organisations",
    description: "Tile action: drill down",
  },
  showListFor: {
    id: "console.metrics.showListFor",
    defaultMessage: "Show the organisations: {metric}",
    description: "Accessible name of a tile's drill-down button",
  },
  trend: {
    id: "console.metrics.trend",
    defaultMessage: "Trend: {metric}",
    description: "Chart heading",
  },
  chartLabel: {
    id: "console.metrics.chartLabel",
    defaultMessage: "{metric} by day, last {days} days",
    description: "Accessible name of the trend chart",
  },
  range: { id: "console.metrics.range", defaultMessage: "Period", description: "Chart period" },
  days: {
    id: "console.metrics.days",
    defaultMessage: "{days} days",
    description: "Chart period option",
  },
  drillTitle: {
    id: "console.metrics.drillTitle",
    defaultMessage: "{metric}: {count, plural, one {# organisation} other {# organisations}}",
    description: "Drill-down heading",
  },
  date: { id: "console.metrics.date", defaultMessage: "Date", description: "Data table column" },
  value: { id: "console.metrics.value", defaultMessage: "Value", description: "Data table column" },
  dataTable: {
    id: "console.metrics.dataTable",
    defaultMessage: "Show the figures as a table",
    description: "Disclosure under the chart",
  },
  loadFailed: {
    id: "console.metrics.loadFailed",
    defaultMessage: "We couldn't load the metrics",
    description: "Error",
  },
  retry: { id: "console.metrics.retry", defaultMessage: "Try again", description: "Retry" },
});
