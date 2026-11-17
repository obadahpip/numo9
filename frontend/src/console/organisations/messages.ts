import { defineMessages } from "@/i18n";

/** Console organisations list and detail (U-06-T03/T04). */
export const m = defineMessages({
  title: { id: "console.orgs.title", defaultMessage: "Organisations", description: "Heading" },
  crumb: {
    id: "console.orgs.crumb",
    defaultMessage: "Platform console · Organisations",
    description: "Breadcrumb",
  },
  summary: {
    id: "console.orgs.summary",
    defaultMessage: "{count, plural, one {# organisation} other {# organisations}}",
    description: "How many organisations match",
  },
  search: { id: "console.orgs.search", defaultMessage: "Name", description: "Filter label" },
  status: { id: "console.orgs.status", defaultMessage: "Status", description: "Filter/column" },
  package: { id: "console.orgs.package", defaultMessage: "Package", description: "Filter/column" },
  province: {
    id: "console.orgs.province",
    defaultMessage: "Province",
    description: "Filter/column",
  },
  createdFrom: {
    id: "console.orgs.createdFrom",
    defaultMessage: "Created from",
    description: "Filter label",
  },
  createdTo: {
    id: "console.orgs.createdTo",
    defaultMessage: "Created to",
    description: "Filter label",
  },
  any: { id: "console.orgs.any", defaultMessage: "Any", description: "Filter: no restriction" },
  name: { id: "console.orgs.name", defaultMessage: "Organisation", description: "Column" },
  created: { id: "console.orgs.created", defaultMessage: "Created", description: "Column" },
  demo: {
    id: "console.orgs.demo",
    defaultMessage: "Demo",
    description: "Badge: demo organisation",
  },
  none: { id: "console.orgs.none", defaultMessage: "—", description: "No value" },
  previous: { id: "console.orgs.previous", defaultMessage: "Previous", description: "Pager" },
  next: { id: "console.orgs.next", defaultMessage: "Next", description: "Pager" },
  pageOf: {
    id: "console.orgs.pageOf",
    defaultMessage: "Page {page} of {pages}",
    description: "Pager",
  },
  loadFailed: {
    id: "console.orgs.loadFailed",
    defaultMessage: "The organisations couldn't be loaded.",
    description: "Error",
  },
  retry: { id: "console.orgs.retry", defaultMessage: "Try again", description: "Retry" },
  detailCrumb: {
    id: "console.orgs.detailCrumb",
    defaultMessage: "Platform console · Organisation",
    description: "Breadcrumb of an organisation's detail",
  },
  subscription: {
    id: "console.orgs.subscription",
    defaultMessage: "Subscription",
    description: "Section heading",
  },
  openPackage: {
    id: "console.orgs.openPackage",
    defaultMessage: "Open the {package} package",
    description: "Link from an organisation's subscription to the package editor",
  },
  noSubscription: {
    id: "console.orgs.noSubscription",
    defaultMessage: "No subscription.",
    description: "Organisation without a subscription",
  },
  timeline: {
    id: "console.orgs.timeline",
    defaultMessage: "Subscription history",
    description: "Section heading: state history",
  },
  trialStarted: {
    id: "console.orgs.trialStarted",
    defaultMessage: "Free trial started",
    description: "Timeline item",
  },
  subscribed: {
    id: "console.orgs.subscribed",
    defaultMessage: "Subscription created ({detail})",
    description: "Timeline item",
  },
  statusChanged: {
    id: "console.orgs.statusChanged",
    defaultMessage: "Status changed: {detail}",
    description: "Timeline item",
  },
  converted: {
    id: "console.orgs.converted",
    defaultMessage: "Trial converted — first payment",
    description: "Timeline item",
  },
  users: { id: "console.orgs.users", defaultMessage: "Users", description: "Section heading" },
  role: { id: "console.orgs.role", defaultMessage: "Role", description: "Column" },
  lastLogin: {
    id: "console.orgs.lastLogin",
    defaultMessage: "Last sign-in",
    description: "Column",
  },
  practices: {
    id: "console.orgs.practices",
    defaultMessage: "Practices serving it",
    description: "Section heading",
  },
  practiceLine: {
    id: "console.orgs.practiceLine",
    defaultMessage:
      "{name} — {role}, {staff, plural, one {# staff member} other {# staff}} assigned{active, select, true {} other { (switched off)}}",
    description: "One practice assignment",
  },
  audit: { id: "console.orgs.audit", defaultMessage: "Audit log", description: "Section heading" },
  auditNone: {
    id: "console.orgs.auditNone",
    defaultMessage: "No events yet.",
    description: "Empty audit log",
  },
  back: {
    id: "console.orgs.back",
    defaultMessage: "All organisations",
    description: "Link back to the list",
  },
  headline: {
    id: "console.orgs.headline",
    defaultMessage: "{status} · {province} · created {created}",
    description: "Organisation detail: status, province, creation date",
  },
  userLine: {
    id: "console.orgs.userLine",
    defaultMessage: "{name} · {email} · role: {role} · last sign-in: {last}",
    description: "One user of the organisation",
  },
  eventLine: {
    id: "console.orgs.eventLine",
    defaultMessage: "{actor} · {action} · {record}",
    description: "One audit event: who, what, which record",
  },
  ends: {
    id: "console.orgs.ends",
    defaultMessage: "{status} · {package} · period ends {date}",
    description: "Subscription summary",
  },
});
