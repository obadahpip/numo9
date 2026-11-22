import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";

import { chartAccounts, sampleAccounts, sampleTaxCodes } from "../pickers/fixtures";
import { ToastProvider } from "../primitives/Toast";
import {
  DocumentLines,
  newDocumentLine,
  problemCells,
  type DocumentGridLine,
} from "./DocumentLines";
import { DocumentTotals, type DocumentDiscountType } from "./DocumentTotals";
import {
  documentLabels,
  journalLabels,
  roughAmounts,
  sampleDocumentLines,
  sampleJournal,
  pseudoLabels,
  sampleTotals,
  totalsLabels,
} from "./fixtures";
import { JournalLines } from "./JournalLines";
import { LineGrid, localColumnStore, type DocumentLine } from "./LineGrid";

/**
 * LineGrid (A-10-T11): the one document line editor. Keys: ↑/↓ between lines, Enter down (adds a
 * line at the end), Alt+Shift+↑/↓ moves a line, Alt+↓ opens the account list. Spec for D-01/E-02:
 * docs/design/line-grid.md.
 */
const meta: Meta = { title: "Data/LineGrid", parameters: { layout: "padded" } };
export default meta;
type Story = StoryObj;

function JournalDemo() {
  const [lines, setLines] = useState(sampleJournal);
  return (
    <JournalLines
      lines={lines}
      onChange={setLines}
      accounts={sampleAccounts}
      labels={journalLabels}
      locale="en-CA"
    />
  );
}
export const Journal: Story = { render: () => <JournalDemo /> };

let n = 0;
function InvoiceShape() {
  const [lines, setLines] = useState<DocumentLine[]>([
    { id: "i1", description: "Kitchen cabinets — install", qty: "1", amount: "4800.00" },
    { id: "i2", description: "Hardware", qty: "24", amount: "312.00" },
  ]);
  return (
    <LineGrid
      lines={lines}
      onChange={setLines}
      columns={[
        { id: "description", header: "Description", kind: "text" },
        { id: "qty", header: "Qty", kind: "text", width: 80 },
        { id: "note", header: "Internal note", kind: "text", optional: true },
        { id: "amount", header: "Amount", kind: "money", total: true, width: 140 },
      ]}
      defaultHiddenColumns={["note"]}
      newLine={() => ({ id: `n${++n}`, description: "", qty: "", amount: null })}
      labels={journalLabels}
      locale="en-CA"
    />
  );
}
/** The shape D-01 builds on (columns per docs/design/line-grid.md). */
export const InvoiceShapeStory: Story = {
  name: "Invoice shape (D-01 preview)",
  render: () => <InvoiceShape />,
};

const STORE = localColumnStore("numo9.lines.story-user.sales");

function DocumentDemo({
  initial,
  side = "sales",
  readOnly = false,
  problems,
  labels = documentLabels,
}: {
  initial: DocumentGridLine[];
  side?: "sales" | "purchase";
  readOnly?: boolean;
  problems?: Record<string, string[]>;
  labels?: typeof documentLabels;
}) {
  const [lines, setLines] = useState(initial);
  const rates = Object.fromEntries(sampleTaxCodes.map((code) => [code.id, code.rate ?? "0"]));
  return (
    <ToastProvider labels={{ region: "Notifications ({hotkey})", close: "Close" }}>
      <DocumentLines
        lines={lines}
        onChange={setLines}
        side={side}
        date="2026-07-15"
        readOnly={readOnly}
        problems={problems}
        accounts={chartAccounts}
        taxCodes={sampleTaxCodes}
        amounts={roughAmounts(lines, rates)}
        taxWhy={Object.fromEntries(
          lines
            .filter((l) => l.taxCode === "s-on")
            .map((l) => [l.id, "Ontario customer → HST 13 %"]),
        )}
        accountDefaults={{ c4001: "sales.ON.standard", c4002: "sales.ON.standard" }}
        columnStore={STORE}
        labels={labels}
        locale="en-CA"
      />
    </ToastProvider>
  );
}

/**
 * Document lines (D-01-T11): invoice, quote and credit note editor. Ctrl+D duplicates a line,
 * Ctrl+Backspace deletes it (Undo in the toast); Tax amount and Amount are calculated.
 */
export const DocumentLinesStory: Story = {
  name: "Document lines (D-01)",
  render: () => <DocumentDemo initial={sampleDocumentLines} />,
};

/** An empty document: the keyboard-only flow starts here (Playwright fills 5 lines). */
export const DocumentLinesEmpty: Story = {
  name: "Document lines — empty",
  render: () => <DocumentDemo initial={[{ ...newDocumentLine(), id: "first" }]} />,
};

function TotalsDemo() {
  const [discount, setDiscount] = useState<[DocumentDiscountType, string]>(["none", ""]);
  return (
    <DocumentTotals
      value={sampleTotals}
      discountType={discount[0]}
      discountValue={discount[1]}
      onDiscountChange={(type, value) => setDiscount([type, value])}
      labels={totalsLabels}
      locale="en-CA"
    />
  );
}

/** Totals panel (D-01-T14): document discount, tax per component, total in a live region. */
export const DocumentTotalsStory: Story = { name: "Document totals", render: () => <TotalsDemo /> };

/** Read-only (a sent invoice): no controls to change lines, totals still shown. */
export const DocumentLinesReadOnly: Story = {
  name: "Document lines — read-only",
  render: () => <DocumentDemo initial={sampleDocumentLines} readOnly />,
};

/** Cells the server refused (D-01-T06): flagged until fixed. */
export const DocumentLinesProblems: Story = {
  name: "Document lines — server problems",
  render: () => (
    <DocumentDemo
      initial={sampleDocumentLines}
      problems={problemCells(sampleDocumentLines, [
        { line: 2, field: "tax_code" },
        { line: 2, field: "account" },
      ])}
    />
  ),
};

/** A bill (E-02 uses the same grid): expense accounts and purchase codes only. */
export const DocumentLinesPurchase: Story = {
  name: "Document lines — purchases",
  render: () => (
    <DocumentDemo
      side="purchase"
      initial={[
        {
          ...sampleDocumentLines[0]!,
          description: "Printer paper",
          account: "c6080",
          taxCode: "p-on",
        },
      ]}
    />
  ),
};

/** Inclusive document: the total includes the tax (D-01-T14). */
export const DocumentTotalsInclusive: Story = {
  name: "Document totals — tax inclusive",
  render: () => (
    <DocumentTotals
      value={{ ...sampleTotals, total: "5741.30", taxIncluded: true }}
      discountType="percent"
      discountValue="5"
      labels={totalsLabels}
      locale="en-CA"
    />
  ),
};

/** Pseudo-locale (+30 %, D-01-T19): long labels must not clip, in the table or in the cards. */
export const DocumentPseudoLocale: Story = {
  name: "Document lines — pseudo-locale",
  render: () => (
    <div className="flex flex-col gap-4">
      <DocumentDemo initial={sampleDocumentLines} labels={pseudoLabels(documentLabels)} />
      <DocumentTotals
        value={sampleTotals}
        discountType="percent"
        discountValue="5"
        labels={pseudoLabels(totalsLabels)}
        locale="en-CA"
      />
    </div>
  ),
};
