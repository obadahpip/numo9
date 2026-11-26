import { defineMessages } from "@/i18n";

/** Assurance page (K-09-T21). */
export const am = defineMessages({
  title: { id: "assurance.title", defaultMessage: "Assurance", description: "Page heading" },
  intro: {
    id: "assurance.intro",
    defaultMessage:
      "Rules over your books that catch real problems — negative cash, expenses booked by journal, missing tax numbers or lock dates — each explained with its numbers and, where it helps, a correcting entry to review.",
    description: "Text under the heading",
  },
  run: { id: "assurance.run", defaultMessage: "Run the rules", description: "Button: full run" },
  running: {
    id: "assurance.running",
    defaultMessage: "The rules are running. The list refreshes when they finish.",
    description: "Status after Run the rules",
  },
  lastRun: {
    id: "assurance.lastRun",
    defaultMessage: "Last run {when}",
    description: "When the checks last ran",
  },
  neverRun: {
    id: "assurance.neverRun",
    defaultMessage: "The rules haven't run yet.",
    description: "No run so far",
  },
  score: {
    id: "assurance.score",
    defaultMessage: "Assurance score",
    description: "Score card title",
  },
  scoreValue: {
    id: "assurance.scoreValue",
    defaultMessage: "{score} out of 100",
    description: "The score, read out",
  },
  severity: {
    id: "assurance.severity",
    defaultMessage: "{severity, select, critical {Critical} warning {Warning} other {Info}}",
    description: "Severity name",
  },
  count: {
    id: "assurance.count",
    defaultMessage:
      "{severity, select, critical {Critical} warning {Warning} other {Info}}: {count}",
    description: "Open findings of a severity on the score card",
  },
  acknowledgedCount: {
    id: "assurance.acknowledgedCount",
    defaultMessage: "Acknowledged: {count}",
    description: "Acknowledged findings on the score card",
  },
  filters: { id: "assurance.filters", defaultMessage: "Filters", description: "Filter bar label" },
  allSeverities: {
    id: "assurance.allSeverities",
    defaultMessage: "All",
    description: "Severity chip: no severity filter",
  },
  statusLabel: {
    id: "assurance.statusLabel",
    defaultMessage: "Status",
    description: "Status filter",
  },
  status: {
    id: "assurance.status",
    defaultMessage:
      "{status, select, open {Open} acknowledged {Acknowledged} resolved {Resolved} false_positive {False positive} other {Open and acknowledged}}",
    description: "Finding status",
  },
  search: { id: "assurance.search", defaultMessage: "Search", description: "Text search label" },
  searchPlaceholder: {
    id: "assurance.searchPlaceholder",
    defaultMessage: "Rule, account, journal…",
    description: "Text search placeholder",
  },
  groupCount: {
    id: "assurance.groupCount",
    defaultMessage: "{count, plural, one {# finding} other {# findings}}",
    description: "Number of findings of a rule",
  },
  viewSource: { id: "assurance.viewSource", defaultMessage: "View source", description: "Action" },
  proposeFix: { id: "assurance.proposeFix", defaultMessage: "Propose fix", description: "Action" },
  acknowledge: {
    id: "assurance.acknowledge",
    defaultMessage: "Acknowledge",
    description: "Action",
  },
  falsePositive: {
    id: "assurance.falsePositive",
    defaultMessage: "Mark false positive",
    description: "Action",
  },
  reopen: { id: "assurance.reopen", defaultMessage: "Reopen", description: "Action" },
  ackBy: {
    id: "assurance.ackBy",
    defaultMessage: "Acknowledged by {name}",
    description: "Who acknowledged the finding",
  },
  ackByReason: {
    id: "assurance.ackByReason",
    defaultMessage: "Acknowledged by {name} — {reason}",
    description: "Who acknowledged the finding and why",
  },
  fixDrafted: {
    id: "assurance.fixDrafted",
    defaultMessage: "A draft fix is waiting in Journals › Draft.",
    description: "The finding has a draft fix",
  },
  emptyTitle: {
    id: "assurance.emptyTitle",
    defaultMessage: "No findings",
    description: "Empty state title",
  },
  emptyBody: {
    id: "assurance.emptyBody",
    defaultMessage: "Nothing matches these filters. Run the rules again after you post changes.",
    description: "Empty state text",
  },
  loadFailed: {
    id: "assurance.loadFailed",
    defaultMessage: "The findings couldn't be loaded",
    description: "Error state title",
  },
  retry: { id: "assurance.retry", defaultMessage: "Try again", description: "Retry button" },
  failed: {
    id: "assurance.failed",
    defaultMessage: "That didn't work. Try again.",
    description: "Generic action error",
  },
  close: { id: "assurance.close", defaultMessage: "Close", description: "Close a dialog" },
  cancel: { id: "assurance.cancel", defaultMessage: "Cancel", description: "Cancel button" },
  falsePositiveTitle: {
    id: "assurance.falsePositiveTitle",
    defaultMessage: "Mark as a false positive",
    description: "Dialog title",
  },
  falsePositiveHelp: {
    id: "assurance.falsePositiveHelp",
    defaultMessage:
      "Say why this isn't a problem. It stays quiet while it comes back with the same amount; a different amount opens a new finding.",
    description: "Dialog text",
  },
  reason: { id: "assurance.reason", defaultMessage: "Reason", description: "Reason field" },
  save: { id: "assurance.save", defaultMessage: "Save", description: "Save button" },
  fixTitle: {
    id: "assurance.fixTitle",
    defaultMessage: "Proposed fix",
    description: "Fix dialog title",
  },
  fixWhy: {
    id: "assurance.fixWhy",
    defaultMessage: "Why this entry",
    description: "Fix reasoning heading",
  },
  fixDate: {
    id: "assurance.fixDate",
    defaultMessage: "Date {date}",
    description: "Date of the proposed entry",
  },
  account: { id: "assurance.account", defaultMessage: "Account", description: "Column" },
  debit: { id: "assurance.debit", defaultMessage: "Debit", description: "Column" },
  credit: { id: "assurance.credit", defaultMessage: "Credit", description: "Column" },
  totals: {
    id: "assurance.totals",
    defaultMessage: "Totals {debit} / {credit}",
    description: "Totals of the proposed entry",
  },
  alternatives: {
    id: "assurance.alternatives",
    defaultMessage: "Other option: {text}",
    description: "Another proposed entry",
  },
  createDraft: {
    id: "assurance.createDraft",
    defaultMessage: "Create draft journal",
    description: "Turn the proposal into a draft",
  },
  draftCreated: {
    id: "assurance.draftCreated",
    defaultMessage:
      "Draft journal created. Review and post it from Journals › Draft: posting it resolves the finding.",
    description: "After creating the draft",
  },
  openDraft: { id: "assurance.openDraft", defaultMessage: "Open the draft", description: "Link" },
  openRecode: {
    id: "assurance.openRecode",
    defaultMessage: "Open Find & recode",
    description: "Link to the recode tool",
  },
  noFix: {
    id: "assurance.noFix",
    defaultMessage: "There's no entry to propose for this finding now.",
    description: "No proposal",
  },
});
