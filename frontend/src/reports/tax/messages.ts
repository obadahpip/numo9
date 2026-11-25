import { defineMessages } from "@/i18n";

/** Tax reports in the runner (G-05-T10): presets, tie-out card, flags, document links. */
export const tm = defineMessages({
  period: { id: "taxReports.period", defaultMessage: "Tax period", description: "Param label" },
  periodOption: {
    id: "taxReports.periodOption",
    defaultMessage:
      "{period, select, current {Current filing period} last_filed {Last filed period} other {Dates above}}",
    description: "Tax period preset",
  },
  ties: {
    id: "taxReports.ties",
    defaultMessage: "✓ Ties to GL",
    description: "Tie-out card when every difference is 0.00",
  },
  tiesBody: {
    id: "taxReports.tiesBody",
    defaultMessage: "Every tax control account's movement equals the tax reports' total.",
    description: "Tie-out card text when it ties",
  },
  difference: {
    id: "taxReports.difference",
    defaultMessage: "Doesn't tie to GL: difference {amount}",
    description: "Tie-out card when a difference remains",
  },
  differenceBody: {
    id: "taxReports.differenceBody",
    defaultMessage:
      "These journals posted to a tax control account without tax lines. Fix them with a journal that carries the tax code, or reverse them.",
    description: "Tie-out card text when it doesn't tie",
  },
  journalsTitle: {
    id: "taxReports.journalsTitle",
    defaultMessage: "Journals affecting tax accounts — {account}",
    description: "Heading of the offending journals of one control account",
  },
  journalLine: {
    id: "taxReports.journalLine",
    defaultMessage: "{journal} · {date} · {narration} · {amount}",
    description: "One offending journal",
  },
  flagsTitle: {
    id: "taxReports.flagsTitle",
    defaultMessage: "Flagged lines",
    description: "Heading of the audit report's flagged lines",
  },
  flag: {
    id: "taxReports.flag",
    defaultMessage:
      "{flag, select, override {Code changed} late_adjustment {Late adjustment} journal_source {Journal} restricted_itc {Restricted ITC} superseded {Superseded} other {{flag}}}",
    description: "A tax audit flag chip",
  },
  documentsTitle: {
    id: "taxReports.documentsTitle",
    defaultMessage: "Documents",
    description: "Heading of the document links of the tax detail",
  },
  openDocument: {
    id: "taxReports.openDocument",
    defaultMessage: "Open {number}",
    description: "Link to a document from a tax report row",
  },
});
