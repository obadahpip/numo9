import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";

import { sampleAccounts } from "../pickers/fixtures";
import { journalLabels, sampleJournal } from "./fixtures";
import { JournalLines } from "./JournalLines";
import { LineGrid, type DocumentLine } from "./LineGrid";

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
