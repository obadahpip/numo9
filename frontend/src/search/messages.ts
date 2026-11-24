import { defineMessages } from "@/i18n";

export const m = defineMessages({
  button: {
    id: "palette.button",
    defaultMessage: "Search or jump to…",
    description: "Top bar button opening the command palette (Ctrl/⌘+K)",
  },
  keys: {
    id: "palette.keys",
    defaultMessage: "Ctrl+K",
    description: "Keyboard shortcut shown on the top bar button (⌘K on a Mac works too)",
  },
  title: {
    id: "palette.title",
    defaultMessage: "Search",
    description: "Title of the command palette dialog",
  },
  close: { id: "palette.close", defaultMessage: "Close", description: "Close the palette" },
  input: {
    id: "palette.input",
    defaultMessage: "Search contacts, accounts, journals, settings and reports",
    description: "Accessible name and placeholder of the palette's search box",
  },
  hint: {
    id: "palette.hint",
    defaultMessage: "↑ ↓ to move, Enter to open, Esc to close",
    description: "Keyboard hint under the palette list",
  },
  recents: { id: "palette.group.recents", defaultMessage: "Recent", description: "Group" },
  create: { id: "palette.group.create", defaultMessage: "Create", description: "Group" },
  records: { id: "palette.group.records", defaultMessage: "Records", description: "Group" },
  settings: { id: "palette.group.settings", defaultMessage: "Settings", description: "Group" },
  reports: { id: "palette.group.reports", defaultMessage: "Reports", description: "Group" },
  navigation: {
    id: "palette.group.navigation",
    defaultMessage: "Go to",
    description: "Group of navigation entries (modules, pages)",
  },
  searching: {
    id: "palette.searching",
    defaultMessage: "Searching…",
    description: "Palette while results load",
  },
  error: {
    id: "palette.error",
    defaultMessage: "Search isn't available right now. Make sure you're online, then try again.",
    description: "Palette when the search request failed",
  },
  retry: { id: "palette.retry", defaultMessage: "Try again", description: "Retry the search" },
  empty: {
    id: "palette.empty",
    defaultMessage: "Nothing matches “{query}”. Try a name, a code or an amount.",
    description: "Palette found nothing",
  },
  start: {
    id: "palette.start",
    defaultMessage: "Type a name, an account code or an amount.",
    description: "Palette before anything is typed and with no recent picks",
  },
  locked: {
    id: "palette.locked",
    defaultMessage: "{product} isn't in this organisation's package",
    description: "Why a quick-create action is locked (its product is missing from the package)",
  },
  createMenu: {
    id: "palette.createMenu",
    defaultMessage: "Create",
    description: "Accessible name of the top bar's + menu of quick-create actions (F-01-T13)",
  },
  loading: {
    id: "palette.createMenuLoading",
    defaultMessage: "Loading…",
    description: "The + menu while the person's permissions load",
  },
  lockedPrefix: {
    id: "palette.lockedPrefix",
    defaultMessage: "Locked:",
    description: "Screen-reader prefix of the reason a palette item is locked",
  },
  shortcut: {
    id: "palette.shortcut",
    defaultMessage: "Shortcut {keys}",
    description: "Screen-reader text of an item's keyboard shortcut, e.g. Shortcut N C",
  },
  sheetTitle: {
    id: "palette.sheet.title",
    defaultMessage: "Keyboard shortcuts",
    description: "Title of the shortcut sheet opened with ?",
  },
  sheetGeneral: {
    id: "palette.sheet.general",
    defaultMessage: "Everywhere",
    description: "Shortcut sheet section: shortcuts that work on every page",
  },
  sheetCreate: {
    id: "palette.sheet.create",
    defaultMessage: "Create (press N, then the letter)",
    description: "Shortcut sheet section: quick-create shortcuts",
  },
  sheetKeys: { id: "palette.sheet.keys", defaultMessage: "Keys", description: "Column" },
  sheetAction: { id: "palette.sheet.action", defaultMessage: "Action", description: "Column" },
  sheetLater: {
    id: "palette.sheet.later",
    defaultMessage: "Coming soon",
    description: "Next to a shortcut whose screen isn't available yet",
  },
  sheetHelp: {
    id: "palette.sheet.help",
    defaultMessage: "Single-key shortcuts don't work while you're typing in a field.",
    description: "Note under the shortcut sheet",
  },
});
