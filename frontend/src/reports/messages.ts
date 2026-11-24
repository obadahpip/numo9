import { defineMessages, type MessageDescriptor } from "@/i18n";

/** Report home (K-01-T12). */
export const home = defineMessages({
  title: { id: "reports.home.title", defaultMessage: "Reports", description: "Page heading" },
  intro: {
    id: "reports.home.intro",
    defaultMessage:
      "One place for every financial, tax and operational report. Star the ones you use most.",
    description: "Text under the reports heading",
  },
  search: {
    id: "reports.home.search",
    defaultMessage: "Search reports",
    description: "Search box label on the report home",
  },
  noMatch: {
    id: "reports.home.noMatch",
    defaultMessage: "No report matches “{query}”.",
    description: "Search found nothing",
  },
  tabs: { id: "reports.home.tabs", defaultMessage: "Report views", description: "Tab list name" },
  standard: { id: "reports.home.standard", defaultMessage: "Standard", description: "Tab" },
  drafts: {
    id: "reports.home.drafts",
    defaultMessage: "Drafts",
    description: "Tab: draft layouts",
  },
  published: {
    id: "reports.home.published",
    defaultMessage: "Published",
    description: "Tab: published (frozen) layouts",
  },
  custom: {
    id: "reports.home.custom",
    defaultMessage: "Custom",
    description: "Tab: saved variants",
  },
  categories: {
    id: "reports.home.categories",
    defaultMessage: "Categories",
    description: "Category filter group name",
  },
  all: {
    id: "reports.home.all",
    defaultMessage: "All",
    description: "Category filter: every report",
  },
  favourites: {
    id: "reports.home.favourites",
    defaultMessage: "Favourites",
    description: "Category filter: starred reports",
  },
  noFavourites: {
    id: "reports.home.noFavourites",
    defaultMessage: "Star a report to keep it here.",
    description: "Favourites filter with no starred report",
  },
  showDescriptions: {
    id: "reports.home.showDescriptions",
    defaultMessage: "Show descriptions",
    description: "Switch: one-line description under each report",
  },
  star: {
    id: "reports.home.star",
    defaultMessage: "Add {name} to favourites",
    description: "Star button (not starred yet)",
  },
  unstar: {
    id: "reports.home.unstar",
    defaultMessage: "Remove {name} from favourites",
    description: "Star button (starred)",
  },
  gated: {
    id: "reports.home.gated",
    defaultMessage: "Part of {product} — not in this organisation's package",
    description: "A report whose product the package lacks (shown, never hidden)",
  },
  noLayouts: {
    id: "reports.home.noLayouts",
    defaultMessage: "No saved layouts here yet. Open a report and use Edit layout to save one.",
    description: "Empty Drafts / Published / Custom tab",
  },
  layoutVersion: {
    id: "reports.home.layoutVersion",
    defaultMessage: "{report} · version {version}",
    description: "A saved layout's report and version",
  },
  loadFailed: {
    id: "reports.home.loadFailed",
    defaultMessage: "Reports couldn't be loaded",
    description: "Error title",
  },
  loadFailedBody: {
    id: "reports.home.loadFailedBody",
    defaultMessage: "Nothing was changed. Try again in a moment.",
    description: "Error body",
  },
  retry: { id: "reports.home.retry", defaultMessage: "Try again", description: "Button" },
});

export const categoryLabels: Record<string, MessageDescriptor> = defineMessages({
  financial: {
    id: "reports.category.financial",
    defaultMessage: "Financial",
    description: "Report category",
  },
  tax: { id: "reports.category.tax", defaultMessage: "Tax", description: "Report category" },
  sales: { id: "reports.category.sales", defaultMessage: "Sales", description: "Report category" },
  purchases: {
    id: "reports.category.purchases",
    defaultMessage: "Purchases",
    description: "Report category",
  },
  banking: {
    id: "reports.category.banking",
    defaultMessage: "Banking",
    description: "Report category",
  },
  payroll: {
    id: "reports.category.payroll",
    defaultMessage: "Payroll",
    description: "Report category",
  },
});
