import { defineMessages } from "@/i18n";

/** Packages list and package editor (U-02-T09). */
export const pm = defineMessages({
  title: {
    id: "packages.list.title",
    defaultMessage: "Packages and prices",
    description: "Heading of the platform console's packages screen",
  },
  intro: {
    id: "packages.list.intro",
    defaultMessage:
      "What organisations subscribe to. Packages are made of whole products; Practice and Client portal are free and part of every package.",
    description: "Text under the packages heading",
  },
  newPackage: {
    id: "packages.list.new",
    defaultMessage: "New package",
    description: "Button: create a package",
  },
  colPackage: { id: "packages.list.colPackage", defaultMessage: "Package", description: "Column" },
  colStatus: { id: "packages.list.colStatus", defaultMessage: "Status", description: "Column" },
  colProducts: {
    id: "packages.list.colProducts",
    defaultMessage: "Products",
    description: "Column",
  },
  colMonthly: {
    id: "packages.list.colMonthly",
    defaultMessage: "Monthly",
    description: "Column: monthly price in force today",
  },
  colAnnual: {
    id: "packages.list.colAnnual",
    defaultMessage: "Annual",
    description: "Column: annual price in force today",
  },
  colSubscribers: {
    id: "packages.list.colSubscribers",
    defaultMessage: "Subscribers",
    description: "Column: subscriptions that haven't ended",
  },
  noPrice: {
    id: "packages.list.noPrice",
    defaultMessage: "No price",
    description: "Cell: the package has no price in force today for this interval",
  },
  emptyTitle: {
    id: "packages.list.emptyTitle",
    defaultMessage: "No packages yet",
    description: "Empty state title",
  },
  emptyBody: {
    id: "packages.list.emptyBody",
    defaultMessage: "Packages are what organisations subscribe to. Create the first one.",
    description: "Empty state text",
  },
  createFirst: {
    id: "packages.list.createFirst",
    defaultMessage: "Create a package",
    description: "Empty state action",
  },
  loading: {
    id: "packages.list.loading",
    defaultMessage: "Loading packages…",
    description: "Loading state",
  },
  loadFailed: {
    id: "packages.list.loadFailed",
    defaultMessage: "The packages couldn't be loaded. Refresh the page to try again.",
    description: "The request failed",
  },
  refusedTitle: {
    id: "packages.list.refusedTitle",
    defaultMessage: "You can't manage packages and prices",
    description: "Title when the person lacks platform.catalogue.manage",
  },
  open: {
    id: "packages.list.open",
    defaultMessage: "Open {name}",
    description: "Accessible name of the link to a package",
  },
  // ---- editor --------------------------------------------------------------------------------
  back: {
    id: "packages.editor.back",
    defaultMessage: "All packages",
    description: "Link back to the packages list",
  },
  newTitle: {
    id: "packages.editor.newTitle",
    defaultMessage: "New package",
    description: "Heading of the editor for a new package",
  },
  details: {
    id: "packages.editor.details",
    defaultMessage: "Package details",
    description: "Section heading",
  },
  code: { id: "packages.editor.code", defaultMessage: "Code", description: "Field label" },
  codeHint: {
    id: "packages.editor.codeHint",
    defaultMessage: "Lower-case letters, digits and _. It never changes once the package is saved.",
    description: "Hint under the code field",
  },
  nameEn: {
    id: "packages.editor.nameEn",
    defaultMessage: "Name (English)",
    description: "Field label",
  },
  nameFr: {
    id: "packages.editor.nameFr",
    defaultMessage: "Name (French)",
    description: "Field label",
  },
  descriptionEn: {
    id: "packages.editor.descriptionEn",
    defaultMessage: "Description (English)",
    description: "Field label",
  },
  descriptionFr: {
    id: "packages.editor.descriptionFr",
    defaultMessage: "Description (French)",
    description: "Field label",
  },
  frenchHint: {
    id: "packages.editor.frenchHint",
    defaultMessage: "Optional: the English text is shown in French until you enter it.",
    description: "Hint under the French fields",
  },
  products: {
    id: "packages.editor.products",
    defaultMessage: "Products",
    description: "Section heading",
  },
  productsHint: {
    id: "packages.editor.productsHint",
    defaultMessage: "Included free in every package: {free}.",
    description: "Text under the products heading listing the free product sets",
  },
  featureCount: {
    id: "packages.editor.featureCount",
    defaultMessage:
      "{count, plural, =0 {Feature keys arrive when it's built} one {# feature key} other {# feature keys}}",
    description: "Product card: number of feature keys",
  },
  plannedProduct: {
    id: "packages.editor.plannedProduct",
    defaultMessage: "Planned — can't be added yet",
    description: "Product card of a planned companion app",
  },
  include: {
    id: "packages.editor.include",
    defaultMessage: "Include {product}",
    description: "Accessible name of the product card switch",
  },
  limits: { id: "packages.editor.limits", defaultMessage: "Limits", description: "Section" },
  maxUsers: {
    id: "packages.editor.maxUsers",
    defaultMessage: "Organisation users",
    description: "Field label: maximum organisation users",
  },
  unlimited: {
    id: "packages.editor.unlimited",
    defaultMessage: "Unlimited",
    description: "Checkbox: no user limit",
  },
  maxUsersHint: {
    id: "packages.editor.maxUsersHint",
    defaultMessage: "Practice users (accountants) are never counted.",
    description: "Hint under the user limit",
  },
  maxUsersInvalid: {
    id: "packages.editor.maxUsersInvalid",
    defaultMessage: "Enter a whole number of 1 or more, or tick Unlimited.",
    description: "Field error",
  },
  founding: {
    id: "packages.editor.founding",
    defaultMessage: "Founding offer",
    description: "Switch label",
  },
  foundingHint: {
    id: "packages.editor.foundingHint",
    defaultMessage: "The first 1,000 organisations on this package get every product.",
    description: "Switch description",
  },
  preview: {
    id: "packages.editor.preview",
    defaultMessage: "Preview — public pricing card",
    description: "Heading of the live preview",
  },
  save: { id: "packages.editor.save", defaultMessage: "Save", description: "Button" },
  saveDraft: {
    id: "packages.editor.saveDraft",
    defaultMessage: "Save draft",
    description: "Button: create the package as a draft",
  },
  activate: {
    id: "packages.editor.activate",
    defaultMessage: "Activate package",
    description: "Button: offer the package at sign-up",
  },
  retire: {
    id: "packages.editor.retire",
    defaultMessage: "Retire package",
    description: "Button: hide the package from sign-up",
  },
  delete: {
    id: "packages.editor.delete",
    defaultMessage: "Delete draft",
    description: "Button: delete a draft package",
  },
  deleteTitle: {
    id: "packages.editor.deleteTitle",
    defaultMessage: "Delete {name}?",
    description: "Delete confirmation title",
  },
  deleteBody: {
    id: "packages.editor.deleteBody",
    defaultMessage: "The draft, its products and its prices are deleted. This can't be undone.",
    description: "Delete confirmation text",
  },
  retireTitle: {
    id: "packages.editor.retireTitle",
    defaultMessage: "Retire {name}?",
    description: "Retire confirmation title",
  },
  retireBody: {
    id: "packages.editor.retireBody",
    defaultMessage:
      "It's hidden from sign-up and the pricing page. {count, plural, =0 {Nobody subscribes to it.} one {The organisation that subscribes keeps it.} other {The # organisations that subscribe keep it.}}",
    description: "Retire confirmation text",
  },
  cancel: { id: "packages.editor.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "packages.editor.close", defaultMessage: "Close", description: "Button" },
  saved: {
    id: "packages.editor.saved",
    defaultMessage: "{name} saved.",
    description: "Status after saving",
  },
  activated: {
    id: "packages.editor.activated",
    defaultMessage: "{name} is offered at sign-up.",
    description: "Status after activating",
  },
  retired: {
    id: "packages.editor.retired",
    defaultMessage: "{name} is retired: hidden from sign-up; subscribers keep it.",
    description: "Status after retiring",
  },
  retiredNotice: {
    id: "packages.editor.retiredNotice",
    defaultMessage:
      "Retired — hidden from sign-up. {count, plural, =0 {Nobody subscribes to it.} one {# organisation keeps its subscription.} other {# organisations keep their subscription.}}",
    description: "Notice on a retired package",
  },
  failed: {
    id: "packages.editor.failed",
    defaultMessage: "That didn't work. Try again.",
    description: "Generic failure",
  },
  fixErrors: {
    id: "packages.editor.fixErrors",
    defaultMessage: "Some fields need attention. Fix them and save again.",
    description: "Shown when the API returned field errors",
  },
  notFoundTitle: {
    id: "packages.editor.notFoundTitle",
    defaultMessage: "This package doesn't exist",
    description: "Title when the package code is unknown",
  },
  notFoundBody: {
    id: "packages.editor.notFoundBody",
    defaultMessage: "It may have been deleted. Open the list of packages.",
    description: "Text when the package code is unknown",
  },
  // ---- pricing card --------------------------------------------------------------------------
  cardMonthly: {
    id: "packages.card.monthly",
    defaultMessage: "Monthly",
    description: "Pricing card interval toggle",
  },
  cardAnnual: {
    id: "packages.card.annual",
    defaultMessage: "Annual",
    description: "Pricing card interval toggle",
  },
  cardInterval: {
    id: "packages.card.interval",
    defaultMessage: "Billing interval",
    description: "Accessible name of the monthly/annual toggle",
  },
  cardPerMonth: {
    id: "packages.card.perMonth",
    defaultMessage: "/ month, plus GST/HST",
    description: "After the monthly price",
  },
  cardPerYear: {
    id: "packages.card.perYear",
    defaultMessage: "/ year, plus GST/HST",
    description: "After the annual price",
  },
  cardNoPrice: {
    id: "packages.card.noPrice",
    defaultMessage: "Price to come",
    description: "Pricing card without a price for the interval",
  },
  cardFree: {
    id: "packages.card.free",
    defaultMessage: "{products} (free)",
    description: "Pricing card line: the free product sets",
  },
  cardUsers: {
    id: "packages.card.users",
    defaultMessage:
      "{count, plural, one {Up to # organisation user} other {Up to # organisation users}}",
    description: "Pricing card line: user limit",
  },
  cardUnlimitedUsers: {
    id: "packages.card.unlimitedUsers",
    defaultMessage: "Unlimited organisation users",
    description: "Pricing card line: no user limit",
  },
  cardFounding: {
    id: "packages.card.founding",
    defaultMessage: "Founding offer",
    description: "Badge on the pricing card",
  },
  cardTrial: {
    id: "packages.card.trial",
    defaultMessage: "Start free trial",
    description: "Pricing card button (preview only)",
  },
  cardUntitled: {
    id: "packages.card.untitled",
    defaultMessage: "Package name",
    description: "Pricing card placeholder before a name is entered",
  },
});

/** Price timeline and the schedule dialog (U-02-T10). */
export const tm = defineMessages({
  title: {
    id: "packages.prices.title",
    defaultMessage: "Prices",
    description: "Heading of the price timeline",
  },
  intro: {
    id: "packages.prices.intro",
    defaultMessage:
      "CAD, before GST/HST. A new price applies to each subscription at its first renewal on or after its start date.",
    description: "Text under the prices heading",
  },
  schedule: {
    id: "packages.prices.schedule",
    defaultMessage: "Schedule a price change",
    description: "Button and dialog title",
  },
  monthly: {
    id: "packages.prices.monthly",
    defaultMessage: "Monthly",
    description: "Timeline row heading",
  },
  annual: {
    id: "packages.prices.annual",
    defaultMessage: "Annual",
    description: "Timeline row heading",
  },
  today: {
    id: "packages.prices.today",
    defaultMessage: "Today {date}",
    description: "Label of the today marker on the timeline",
  },
  noVersions: {
    id: "packages.prices.noVersions",
    defaultMessage: "No price yet for this interval.",
    description: "Empty timeline row",
  },
  range: {
    id: "packages.prices.range",
    defaultMessage: "{start} – {end}",
    description: "Dates of a price version: first and last day (or 'No end date')",
  },
  noEnd: {
    id: "packages.prices.noEnd",
    defaultMessage: "No end date",
    description: "Label at the end of an open price version",
  },
  version: {
    id: "packages.prices.version",
    defaultMessage:
      "{amount} from {start}{end, select, none {, no end date} other { until {end}}} — {state, select, current {in force today} scheduled {scheduled} other {ended}}",
    description: "Accessible description of one price version",
  },
  stateCurrent: {
    id: "packages.prices.stateCurrent",
    defaultMessage: "In force today",
    description: "Price version state",
  },
  stateScheduled: {
    id: "packages.prices.stateScheduled",
    defaultMessage: "Scheduled",
    description: "Price version state",
  },
  statePast: {
    id: "packages.prices.statePast",
    defaultMessage: "Ended",
    description: "Price version state",
  },
  deleteScheduled: {
    id: "packages.prices.deleteScheduled",
    defaultMessage: "Delete the {amount} price starting {start}",
    description: "Accessible name of the delete button of a scheduled price",
  },
  deleteShort: {
    id: "packages.prices.deleteShort",
    defaultMessage: "Delete",
    description: "Button: delete a scheduled price",
  },
  interval: {
    id: "packages.prices.interval",
    defaultMessage: "Billing interval",
    description: "Field label",
  },
  amount: {
    id: "packages.prices.amount",
    defaultMessage: "New price (CAD)",
    description: "Field label",
  },
  amountInvalid: {
    id: "packages.prices.amountInvalid",
    defaultMessage: "Enter an amount, for example 49.00.",
    description: "Field error",
  },
  start: {
    id: "packages.prices.start",
    defaultMessage: "Starts on",
    description: "Field label",
  },
  startHint: {
    id: "packages.prices.startHint",
    defaultMessage: "First day the new price applies.",
    description: "Hint under the start date",
  },
  startInvalid: {
    id: "packages.prices.startInvalid",
    defaultMessage: "Choose the date the new price starts.",
    description: "Field error",
  },
  affected: {
    id: "packages.prices.affected",
    defaultMessage:
      "{count, plural, =0 {No subscriptions affected yet} one {# subscription affected at its next renewal} other {# subscriptions affected at their next renewal}}",
    description: "Impact of a scheduled price, from the API",
  },
  keepsOld: {
    id: "packages.prices.keepsOld",
    defaultMessage: "Renewals before {date} keep {amount}.",
    description: "Impact detail when a price is in force before the date",
  },
  grandfathered: {
    id: "packages.prices.grandfathered",
    defaultMessage: "Grandfathered subscriptions never change.",
    description: "Impact detail",
  },
  checking: {
    id: "packages.prices.checking",
    defaultMessage: "Counting the subscriptions affected…",
    description: "While the impact is loading",
  },
  submit: {
    id: "packages.prices.submit",
    defaultMessage: "Schedule price",
    description: "Dialog button",
  },
  scheduled: {
    id: "packages.prices.scheduled",
    defaultMessage:
      "{amount} {interval, select, month {monthly} other {annual}} price scheduled from {date}.",
    description: "Status after scheduling a price",
  },
  deleted: {
    id: "packages.prices.deleted",
    defaultMessage: "The scheduled price was deleted.",
    description: "Status after deleting a scheduled price",
  },
});

/** Promo codes (U-02-T11). */
export const om = defineMessages({
  title: {
    id: "packages.promos.title",
    defaultMessage: "Promo codes",
    description: "Heading of the promo codes screen",
  },
  intro: {
    id: "packages.promos.intro",
    defaultMessage: "Discounts organisations enter at checkout. Codes are case-insensitive.",
    description: "Text under the heading",
  },
  newCode: {
    id: "packages.promos.new",
    defaultMessage: "New promo code",
    description: "Button and dialog title",
  },
  colCode: { id: "packages.promos.colCode", defaultMessage: "Code", description: "Column" },
  colDiscount: {
    id: "packages.promos.colDiscount",
    defaultMessage: "Discount",
    description: "Column",
  },
  colDuration: {
    id: "packages.promos.colDuration",
    defaultMessage: "Duration",
    description: "Column",
  },
  colPackages: {
    id: "packages.promos.colPackages",
    defaultMessage: "Packages",
    description: "Column",
  },
  colUsed: { id: "packages.promos.colUsed", defaultMessage: "Used", description: "Column" },
  colExpires: {
    id: "packages.promos.colExpires",
    defaultMessage: "Expires",
    description: "Column",
  },
  colStatus: { id: "packages.promos.colStatus", defaultMessage: "Status", description: "Column" },
  colActions: {
    id: "packages.promos.colActions",
    defaultMessage: "Actions",
    description: "Column",
  },
  percentOff: {
    id: "packages.promos.percentOff",
    defaultMessage: "{percent}% off",
    description: "Discount cell: percent",
  },
  amountOff: {
    id: "packages.promos.amountOff",
    defaultMessage: "{amount} off",
    description: "Discount cell: fixed amount",
  },
  months: {
    id: "packages.promos.months",
    defaultMessage: "{count, plural, one {# month} other {# months}}",
    description: "Duration cell: number of months",
  },
  anyPackage: {
    id: "packages.promos.anyPackage",
    defaultMessage: "Any package",
    description: "Packages cell: no restriction",
  },
  usage: {
    id: "packages.promos.usage",
    defaultMessage: "{used} of {max}",
    description: "Usage under the bar",
  },
  usageNoLimit: {
    id: "packages.promos.usageNoLimit",
    defaultMessage: "{used} · no limit",
    description: "Usage of a code without a maximum",
  },
  usageLabel: {
    id: "packages.promos.usageLabel",
    defaultMessage: "Uses of {code}",
    description: "Accessible name of the usage bar",
  },
  never: {
    id: "packages.promos.never",
    defaultMessage: "Never",
    description: "Expires cell: no expiry",
  },
  expire: {
    id: "packages.promos.expire",
    defaultMessage: "Expire",
    description: "Button: end an active code now",
  },
  expireLabel: {
    id: "packages.promos.expireLabel",
    defaultMessage: "Expire {code} now",
    description: "Accessible name of the expire button",
  },
  expired: {
    id: "packages.promos.expired",
    defaultMessage: "{code} has expired. Redemptions already made are kept.",
    description: "Status after expiring a code",
  },
  created: {
    id: "packages.promos.created",
    defaultMessage: "{code} created.",
    description: "Status after creating a code",
  },
  emptyTitle: {
    id: "packages.promos.emptyTitle",
    defaultMessage: "No promo codes yet",
    description: "Empty state title",
  },
  emptyBody: {
    id: "packages.promos.emptyBody",
    defaultMessage: "Create one for a launch, an accountant partner or a campaign.",
    description: "Empty state text",
  },
  loading: {
    id: "packages.promos.loading",
    defaultMessage: "Loading promo codes…",
    description: "Loading state",
  },
  loadFailed: {
    id: "packages.promos.loadFailed",
    defaultMessage: "The promo codes couldn't be loaded. Refresh the page to try again.",
    description: "The request failed",
  },
  // ---- create dialog --------------------------------------------------------------------------
  code: { id: "packages.promos.code", defaultMessage: "Code", description: "Field label" },
  codeHint: {
    id: "packages.promos.codeHint",
    defaultMessage: "3–40 letters, digits, - and _. Stored in capitals.",
    description: "Hint",
  },
  description: {
    id: "packages.promos.description",
    defaultMessage: "Description (optional)",
    description: "Field label",
  },
  kind: { id: "packages.promos.kind", defaultMessage: "Discount", description: "Field label" },
  kindPercent: {
    id: "packages.promos.kindPercent",
    defaultMessage: "Percent off",
    description: "Option",
  },
  kindFixed: {
    id: "packages.promos.kindFixed",
    defaultMessage: "Fixed amount off",
    description: "Option",
  },
  percent: {
    id: "packages.promos.percent",
    defaultMessage: "Percentage",
    description: "Field label",
  },
  amount: {
    id: "packages.promos.amount",
    defaultMessage: "Amount off (CAD)",
    description: "Field label",
  },
  duration: {
    id: "packages.promos.duration",
    defaultMessage: "Duration",
    description: "Field label",
  },
  durationOnce: {
    id: "packages.promos.durationOnce",
    defaultMessage: "Once",
    description: "Option",
  },
  durationRepeating: {
    id: "packages.promos.durationRepeating",
    defaultMessage: "Number of months",
    description: "Option",
  },
  durationForever: {
    id: "packages.promos.durationForever",
    defaultMessage: "Forever",
    description: "Option",
  },
  monthsField: {
    id: "packages.promos.monthsField",
    defaultMessage: "Months",
    description: "Field label",
  },
  maxUses: {
    id: "packages.promos.maxUses",
    defaultMessage: "Maximum uses (optional)",
    description: "Field label",
  },
  expiresOn: {
    id: "packages.promos.expiresOn",
    defaultMessage: "Expires on (optional)",
    description: "Field label",
  },
  expiresHint: {
    id: "packages.promos.expiresHint",
    defaultMessage: "The code works until the end of this day (Toronto time).",
    description: "Hint",
  },
  packages: {
    id: "packages.promos.packages",
    defaultMessage: "Packages",
    description: "Fieldset legend",
  },
  packagesHint: {
    id: "packages.promos.packagesHint",
    defaultMessage: "Leave every box empty for a code that works on every package.",
    description: "Hint",
  },
  number: {
    id: "packages.promos.number",
    defaultMessage: "Enter a whole number.",
    description: "Field error",
  },
  amountInvalid: {
    id: "packages.promos.amountInvalid",
    defaultMessage: "Enter an amount greater than $0.00.",
    description: "Field error",
  },
  create: {
    id: "packages.promos.create",
    defaultMessage: "Create code",
    description: "Dialog button",
  },
});
