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
  // K-09-T22 — proposed-fix drawer
  fixNarration: {
    id: "assurance.fixNarration",
    defaultMessage: "Narration",
    description: "Narration field of the proposed entry",
  },
  fixDateLabel: {
    id: "assurance.fixDateLabel",
    defaultMessage: "Date",
    description: "Date field of the proposed entry",
  },
  fixLines: {
    id: "assurance.fixLines",
    defaultMessage: "Lines of the draft journal",
    description: "Caption of the editable grid",
  },
  description: {
    id: "assurance.description",
    defaultMessage: "Description",
    description: "Column",
  },
  accountOfLine: {
    id: "assurance.accountOfLine",
    defaultMessage: "Account, line {line}",
    description: "Accessible name of a line's account",
  },
  debitOfLine: {
    id: "assurance.debitOfLine",
    defaultMessage: "Debit, line {line}",
    description: "Accessible name of a line's debit",
  },
  creditOfLine: {
    id: "assurance.creditOfLine",
    defaultMessage: "Credit, line {line}",
    description: "Accessible name of a line's credit",
  },
  descriptionOfLine: {
    id: "assurance.descriptionOfLine",
    defaultMessage: "Description, line {line}",
    description: "Accessible name of a line's description",
  },
  removeLine: {
    id: "assurance.removeLine",
    defaultMessage: "Remove line {line}",
    description: "Remove a line of the proposed entry",
  },
  lineActions: {
    id: "assurance.lineActions",
    defaultMessage: "Line actions",
    description: "Header of the remove-line column",
  },
  addLine: { id: "assurance.addLine", defaultMessage: "Add a line", description: "Button" },
  chooseAccount: {
    id: "assurance.chooseAccount",
    defaultMessage: "Choose an account",
    description: "Account placeholder",
  },
  balanced: {
    id: "assurance.balanced",
    defaultMessage: "Balanced",
    description: "Debits equal credits",
  },
  outOfBalance: {
    id: "assurance.outOfBalance",
    defaultMessage: "Out of balance by {amount}",
    description: "Debits differ from credits",
  },
  problem: {
    id: "assurance.problem",
    defaultMessage:
      "{problem, select, amount {Amounts are positive numbers with at most two decimals.} lines {A journal needs at least two lines with an account and an amount.} other {Debits and credits must be equal and not zero.}}",
    description: "Why the draft can't be created yet",
  },
  useAlternative: {
    id: "assurance.useAlternative",
    defaultMessage: "Use this option",
    description: "Load another proposed entry into the grid",
  },
  draftNever: {
    id: "assurance.draftNever",
    defaultMessage: "The entry is saved as a draft: nothing is posted until you post it yourself.",
    description: "Reassurance in the fix drawer",
  },
  openDraftTab: {
    id: "assurance.openDraftTab",
    defaultMessage: "See it in Journals › Draft",
    description: "Link to the journals Draft tab",
  },
  recodeChanges: {
    id: "assurance.recodeChanges",
    defaultMessage: "Suggested change: {changes}",
    description: "The change a recode fix proposes",
  },
  loadingFix: {
    id: "assurance.loadingFix",
    defaultMessage: "Working out the proposed entry…",
    description: "While the fix loads",
  },
  // K-09-T23 — tabs and rule settings
  tabs: { id: "assurance.tabs", defaultMessage: "Assurance views", description: "Tab list label" },
  tabFindings: { id: "assurance.tabFindings", defaultMessage: "Findings", description: "Tab" },
  tabRules: { id: "assurance.tabRules", defaultMessage: "Rule settings", description: "Tab" },
  rulesIntro: {
    id: "assurance.rulesIntro",
    defaultMessage:
      "Switch a rule off, change its severity or its parameters. Changes apply on the next run.",
    description: "Text above the rule settings",
  },
  ruleColumn: { id: "assurance.ruleColumn", defaultMessage: "Rule", description: "Column" },
  onColumn: { id: "assurance.onColumn", defaultMessage: "On", description: "Column" },
  severityColumn: {
    id: "assurance.severityColumn",
    defaultMessage: "Severity",
    description: "Column",
  },
  paramsColumn: {
    id: "assurance.paramsColumn",
    defaultMessage: "Parameters",
    description: "Column",
  },
  ruleOn: {
    id: "assurance.ruleOn",
    defaultMessage: "{rule} is on",
    description: "Accessible name of a rule's toggle",
  },
  severityOf: {
    id: "assurance.severityOf",
    defaultMessage: "Severity of {rule}",
    description: "Accessible name of a rule's severity",
  },
  noParams: {
    id: "assurance.noParams",
    defaultMessage: "No parameters",
    description: "A rule without parameters",
  },
  onPosting: {
    id: "assurance.onPosting",
    defaultMessage: "Also checked on posting",
    description: "The rule runs incrementally",
  },
  codesHint: {
    id: "assurance.codesHint",
    defaultMessage: "Account codes, separated by commas",
    description: "Hint of an account-codes parameter",
  },
  paramProblem: {
    id: "assurance.paramProblem",
    defaultMessage:
      "{kind, select, whole {Enter a whole number.} number {Enter an amount with at most two decimals.} min {Enter at least {min}.} max {Enter at most {max}.} choice {Choose one of the options.} codes {Enter account codes separated by commas.} other {Enter a short text (100 characters at most).}}",
    description: "Why a parameter can't be saved",
  },
  resetDefaults: {
    id: "assurance.resetDefaults",
    defaultMessage: "Reset to defaults",
    description: "Button",
  },
  rulesSaved: {
    id: "assurance.rulesSaved",
    defaultMessage:
      "{count, plural, one {# rule saved.} other {# rules saved.}} Changes apply on the next run.",
    description: "After saving the rule settings",
  },
  rulesUnchanged: {
    id: "assurance.rulesUnchanged",
    defaultMessage: "Nothing to save.",
    description: "Save with no change",
  },
  rulesFixErrors: {
    id: "assurance.rulesFixErrors",
    defaultMessage: "Correct the highlighted parameters before saving.",
    description: "Save refused by validation",
  },
  rulesLoadFailed: {
    id: "assurance.rulesLoadFailed",
    defaultMessage: "The rule settings couldn't be loaded",
    description: "Error state title",
  },
  changed: {
    id: "assurance.changed",
    defaultMessage: "Changed",
    description: "Badge: unsaved change of a rule",
  },
  choice: {
    id: "assurance.choice",
    defaultMessage:
      "{value, select, auto {Automatic} transfer {Transfer from a bank account} shareholder_loan {Shareholder loan} other {{value}}}",
    description: "Option of a choice parameter",
  },
  // K-09-T24 — activity heatmap
  tabActivity: { id: "assurance.tabActivity", defaultMessage: "Activity", description: "Tab" },
  activityTitle: {
    id: "assurance.activityTitle",
    defaultMessage: "Activity in the last 12 months",
    description: "Heatmap heading",
  },
  activityHelp: {
    id: "assurance.activityHelp",
    defaultMessage:
      "Actions recorded in the audit log, per day in the organisation's time zone ({zone}). A dormant administrator stands out.",
    description: "Text under the heatmap heading",
  },
  person: { id: "assurance.person", defaultMessage: "Person", description: "Person filter" },
  everyone: { id: "assurance.everyone", defaultMessage: "Everyone", description: "No filter" },
  heatSummary: {
    id: "assurance.heatSummary",
    defaultMessage:
      "{total, plural, =0 {No actions} one {# action} other {# actions}} from {from} to {to}",
    description: "Accessible summary of the calendar grid",
  },
  heatCell: {
    id: "assurance.heatCell",
    defaultMessage: "{date} · {count, plural, =0 {no actions} one {# action} other {# actions}}",
    description: "Tooltip of a day of the heatmap",
  },
  less: { id: "assurance.less", defaultMessage: "Less", description: "Heatmap legend start" },
  more: { id: "assurance.more", defaultMessage: "More", description: "Heatmap legend end" },
  showTable: {
    id: "assurance.showTable",
    defaultMessage: "Show as table",
    description: "Accessible table alternative of the heatmap",
  },
  hideTable: {
    id: "assurance.hideTable",
    defaultMessage: "Hide the table",
    description: "Hide the table alternative",
  },
  dayColumn: { id: "assurance.dayColumn", defaultMessage: "Date", description: "Column" },
  actionsColumn: {
    id: "assurance.actionsColumn",
    defaultMessage: "Actions",
    description: "Column",
  },
  lastColumn: {
    id: "assurance.lastColumn",
    defaultMessage: "Last activity",
    description: "Column",
  },
  peopleTitle: { id: "assurance.peopleTitle", defaultMessage: "People", description: "Heading" },
  noActivity: {
    id: "assurance.noActivity",
    defaultMessage: "No activity in this period.",
    description: "Empty heatmap",
  },
  activityFailed: {
    id: "assurance.activityFailed",
    defaultMessage: "The activity couldn't be loaded",
    description: "Error state title",
  },
  weekday: {
    id: "assurance.weekday",
    defaultMessage: "{day, select, 0 {Mon} 1 {Tue} 2 {Wed} 3 {Thu} 4 {Fri} 5 {Sat} other {Sun}}",
    description: "Short weekday name of a heatmap row",
  },
});
