import { defineMessages } from "@/i18n";

/** Journals list (K-09-T22: the Draft tab a proposed fix lands in). */
export const jl = defineMessages({
  title: { id: "journals.list.title", defaultMessage: "Journals", description: "Heading" },
  newJournal: {
    id: "journals.list.newJournal",
    defaultMessage: "New journal",
    description: "Link to the journal editor",
  },
  recurring: {
    id: "journals.list.recurring",
    defaultMessage: "Recurring",
    description: "Link to recurring journals",
  },
  tabs: { id: "journals.list.tabs", defaultMessage: "Journal status", description: "Tab list" },
  tab: {
    id: "journals.list.tab",
    defaultMessage:
      "{tab, select, draft {Draft} awaiting_approval {Awaiting approval} posted {Posted} reversed {Reversed} other {All}}",
    description: "Tab of the journals list",
  },
  statusName: {
    id: "journals.list.statusName",
    defaultMessage:
      "{status, select, draft {Draft} awaiting_approval {Awaiting approval} posted {Posted} reversed {Reversed} other {{status}}}",
    description: "Status badge of one journal",
  },
  search: {
    id: "journals.list.search",
    defaultMessage: "Search narration or number",
    description: "Search field",
  },
  number: { id: "journals.list.number", defaultMessage: "Number", description: "Column" },
  date: { id: "journals.list.date", defaultMessage: "Date", description: "Column" },
  narration: { id: "journals.list.narration", defaultMessage: "Narration", description: "Column" },
  type: { id: "journals.list.type", defaultMessage: "Type", description: "Column" },
  status: { id: "journals.list.status", defaultMessage: "Status", description: "Column" },
  total: { id: "journals.list.total", defaultMessage: "Total", description: "Column" },
  draftNumber: {
    id: "journals.list.draftNumber",
    defaultMessage: "Draft",
    description: "A draft has no number yet",
  },
  empty: {
    id: "journals.list.empty",
    defaultMessage: "No journals here",
    description: "Empty tab title",
  },
  emptyBody: {
    id: "journals.list.emptyBody",
    defaultMessage: "Journals with this status appear here.",
    description: "Empty tab text",
  },
  failed: {
    id: "journals.list.failed",
    defaultMessage: "The journals couldn't be loaded",
    description: "Error state",
  },
  retry: { id: "journals.list.retry", defaultMessage: "Try again", description: "Retry button" },
  more: { id: "journals.list.more", defaultMessage: "Show more", description: "Next page" },
  count: {
    id: "journals.list.count",
    defaultMessage: "{count, plural, one {# journal} other {# journals}}",
    description: "How many journals the tab has",
  },
});
