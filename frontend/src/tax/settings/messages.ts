import { defineMessages } from "@/i18n";

export const sm = defineMessages({
  title: {
    id: "tax.settings.title",
    defaultMessage: "Tax registrations and settings",
    description: "Heading of the one tax settings page (G-06)",
  },
  intro: {
    id: "tax.settings.intro",
    defaultMessage:
      "Every tax setting is here and nowhere else: registrations, tax basis, default codes, the quick method and restricted input tax credits.",
    description: "Text under the heading",
  },
  nav: {
    id: "tax.settings.navLabel",
    defaultMessage: "On this page",
    description: "Anchor nav name",
  },
  navRegistrations: {
    id: "tax.settings.nav.registrations",
    defaultMessage: "Business number and registrations",
    description: "Anchor",
  },
  navBasis: { id: "tax.settings.nav.basis", defaultMessage: "Tax basis", description: "Anchor" },
  navDefaults: {
    id: "tax.settings.nav.defaults",
    defaultMessage: "Default codes",
    description: "Anchor",
  },
  navQuick: {
    id: "tax.settings.nav.quick",
    defaultMessage: "Quick method",
    description: "Anchor",
  },
  navItc: {
    id: "tax.settings.nav.itc",
    defaultMessage: "Restricted ITCs",
    description: "Anchor",
  },
  loadFailed: {
    id: "tax.settings.loadFailed",
    defaultMessage: "The tax settings couldn't be loaded.",
    description: "Error state",
  },
  retry: { id: "tax.settings.retry", defaultMessage: "Try again", description: "Button" },
  edit: { id: "tax.settings.edit", defaultMessage: "Edit", description: "Button" },
  editCard: {
    id: "tax.settings.editCard",
    defaultMessage: "Edit {card}",
    description: "Accessible name of a card's Edit button",
  },
  save: { id: "tax.settings.save", defaultMessage: "Save", description: "Button" },
  cancel: { id: "tax.settings.cancel", defaultMessage: "Cancel", description: "Button" },
  saved: {
    id: "tax.settings.saved",
    defaultMessage: "{card} saved",
    description: "Status after saving a card",
  },
  failed: {
    id: "tax.settings.failed",
    defaultMessage: "The change couldn't be saved. Try again.",
    description: "Generic failure",
  },
  notRegistered: {
    id: "tax.settings.notRegistered",
    defaultMessage: "Not registered for GST/HST?",
    description: "Empty state title",
  },
  notRegisteredBody: {
    id: "tax.settings.notRegisteredBody",
    defaultMessage:
      "A business with $30,000 or less in taxable sales over four quarters is a small supplier and doesn't have to register. Until you add a GST/HST registration, new documents use the out-of-scope tax code and no return is prepared.",
    description: "Empty state text: the small-supplier rule",
  },
  basisTitle: { id: "tax.settings.basis.title", defaultMessage: "Tax basis", description: "Card" },
  basisHelp: {
    id: "tax.settings.basis.help",
    defaultMessage:
      "When tax is reported. It is also the default for tax reports; a report can use the other basis and says so.",
    description: "Card help",
  },
  basisValue: {
    id: "tax.settings.basis.value",
    defaultMessage: "{basis, select, cash {Cash} other {Accrual}}",
    description: "Tax basis name",
  },
  basisAccrualHelp: {
    id: "tax.settings.basis.accrualHelp",
    defaultMessage: "Accrual: tax is reported when the invoice or bill is dated.",
    description: "Option help",
  },
  basisCashHelp: {
    id: "tax.settings.basis.cashHelp",
    defaultMessage: "Cash: tax is reported when the payment is received or made.",
    description: "Option help",
  },
  basisLabel: { id: "tax.settings.basis.label", defaultMessage: "Basis", description: "Field" },
  basisReason: {
    id: "tax.settings.basis.reason",
    defaultMessage: "Why the basis changes (at least 10 characters)",
    description: "Field",
  },
  defaultsTitle: {
    id: "tax.settings.defaults.title",
    defaultMessage: "Default codes",
    description: "Card",
  },
  defaultsHelp: {
    id: "tax.settings.defaults.help",
    defaultMessage:
      "The tax code a new line starts with, by the type of its account. An account's own code and the place of supply come first.",
    description: "Card help",
  },
  defaultFor: {
    id: "tax.settings.defaults.for",
    defaultMessage:
      "{side, select, sales {Sales} other {Purchases}} on {type, select, revenue {revenue} expense {expense} asset {asset} liability {liability} other {other}} accounts",
    description: "Label of one default code: side and account type",
  },
  noDefault: {
    id: "tax.settings.defaults.none",
    defaultMessage: "No default",
    description: "Select option / value: no default code",
  },
  rounding: {
    id: "tax.settings.defaults.rounding",
    defaultMessage: "Rounding",
    description: "Field: where tax is rounded to the cent",
  },
  roundingValue: {
    id: "tax.settings.defaults.roundingValue",
    defaultMessage: "{mode, select, document {Per document} other {Per line}}",
    description: "Rounding mode name",
  },
  afterStop: {
    id: "tax.settings.defaults.afterStop",
    defaultMessage: "Sales after filing stops",
    description: "Field: default tax code of new sales once GST/HST filing is stopped (G-03b)",
  },
  afterStopValue: {
    id: "tax.settings.defaults.afterStopValue",
    defaultMessage: "{on, select, true {Out of scope} other {Keep the usual default}}",
    description: "Value of the after-stop default",
  },
  quickTitle: {
    id: "tax.settings.quick.title",
    defaultMessage: "Quick method",
    description: "Card",
  },
  quickHelp: {
    id: "tax.settings.quick.help",
    defaultMessage:
      "The quick method of accounting remits a share of tax-included sales instead of tax collected less input tax credits. Elect it with the CRA first.",
    description: "Card help",
  },
  quickOn: {
    id: "tax.settings.quick.on",
    defaultMessage: "Elected from {date}",
    description: "Value: quick method elected",
  },
  quickOff: {
    id: "tax.settings.quick.off",
    defaultMessage: "Not elected (regular method)",
    description: "Value: quick method not elected",
  },
  quickSwitch: {
    id: "tax.settings.quick.switch",
    defaultMessage: "Quick method elected",
    description: "Switch",
  },
  quickFrom: {
    id: "tax.settings.quick.from",
    defaultMessage: "In effect from",
    description: "Field",
  },
  itcTitle: {
    id: "tax.settings.itc.title",
    defaultMessage: "Restricted input tax credits",
    description: "Card",
  },
  itcHelp: {
    id: "tax.settings.itc.help",
    defaultMessage:
      "Expense accounts where only part of the tax can be claimed, such as meals and entertainment at 50 %.",
    description: "Card help",
  },
  itcTable: {
    id: "tax.settings.itc.table",
    defaultMessage: "Accounts with a restricted input tax credit",
    description: "Accessible name of the table",
  },
  itcAccount: { id: "tax.settings.itc.account", defaultMessage: "Account", description: "Column" },
  itcPct: {
    id: "tax.settings.itc.pct",
    defaultMessage: "Claimable %",
    description: "Column",
  },
  itcPctOf: {
    id: "tax.settings.itc.pctOf",
    defaultMessage: "Claimable % of {account}",
    description: "Accessible name of a percentage field",
  },
  itcNone: {
    id: "tax.settings.itc.none",
    defaultMessage: "No account is restricted: tax on every expense account is claimed in full.",
    description: "Empty list",
  },
  itcAdd: {
    id: "tax.settings.itc.add",
    defaultMessage: "Restrict an account",
    description: "Field: pick an expense account to restrict",
  },
  itcAddButton: { id: "tax.settings.itc.addButton", defaultMessage: "Add", description: "Button" },
  itcLift: {
    id: "tax.settings.itc.lift",
    defaultMessage: "Claim {account} in full",
    description: "Button: lift the restriction",
  },
  itcLiftShort: {
    id: "tax.settings.itc.liftShort",
    defaultMessage: "Remove",
    description: "Button text",
  },
  history: { id: "tax.settings.history", defaultMessage: "History", description: "Button" },
  historyTitle: {
    id: "tax.settings.historyTitle",
    defaultMessage: "Tax settings history",
    description: "Drawer title",
  },
  historyEmpty: {
    id: "tax.settings.historyEmpty",
    defaultMessage: "No change yet.",
    description: "Drawer empty state",
  },
  historyFailed: {
    id: "tax.settings.historyFailed",
    defaultMessage: "The history couldn't be loaded.",
    description: "Drawer error",
  },
  historyReason: {
    id: "tax.settings.historyReason",
    defaultMessage: "Reason: {reason}",
    description: "Drawer: the reason given for a change",
  },
  historyWhat: {
    id: "tax.settings.historyWhat",
    defaultMessage: "{action} · {record}",
    description: "Drawer: what changed and on which record",
  },
  historyJob: {
    id: "tax.settings.historyJob",
    defaultMessage: "{name} (job {id})",
    description: "Drawer: a change written by a background job, with its id",
  },
  close: { id: "tax.settings.close", defaultMessage: "Close", description: "Drawer close" },
});
