import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { sampleAccounts, sampleTaxCodes } from "../pickers/fixtures";
import { ToastProvider } from "../primitives/Toast";
import { expectNoAxeViolations } from "../test/axe";
import { DocumentLines, parseLineDiscount, type DocumentGridLine } from "./DocumentLines";
import { documentLabels, roughAmounts, sampleDocumentLines } from "./fixtures";

const RATES = Object.fromEntries(sampleTaxCodes.map((c) => [c.id, c.rate ?? "0"]));

function Editor({ initial }: { initial: DocumentGridLine[] }) {
  const [lines, setLines] = useState(initial);
  return (
    <ToastProvider labels={{ region: "Notifications", close: "Close" }}>
      <DocumentLines
        lines={lines}
        onChange={setLines}
        side="sales"
        date="2026-07-15"
        accounts={sampleAccounts}
        taxCodes={sampleTaxCodes}
        amounts={roughAmounts(lines, RATES)}
        labels={documentLabels}
        locale="en-CA"
      />
      <output data-testid="state">
        {JSON.stringify(lines.map((l) => [l.id, l.description, l.quantity]))}
      </output>
    </ToastProvider>
  );
}

const state = () =>
  JSON.parse(screen.getByTestId("state").textContent ?? "[]") as [string, string, string][];

describe("DocumentLines (D-01-T11)", () => {
  it("shows the document columns in order and the calculated amounts", () => {
    render(<Editor initial={sampleDocumentLines} />);
    const grid = screen.getByRole("grid", { name: "Invoice lines" });
    const headers = within(grid)
      .getAllByRole("columnheader")
      .map((h) => h.textContent)
      .filter(Boolean);
    expect(headers).toEqual([
      "#",
      "Description",
      "Qty",
      "Unit price",
      "Account",
      "Tax code",
      "Tax amount",
      "Amount",
      "Actions",
    ]);
    // 24 × 13.00 − 10 % = 280.80, HST 36.50
    expect(screen.getByRole("status", { name: "Amount, line 2", exact: true })).toHaveTextContent(
      "$280.80",
    );
    expect(screen.getByRole("status", { name: "Tax amount, line 2" })).toHaveTextContent("$36.50");
  });

  it("Ctrl+D duplicates the line under it and announces it", async () => {
    const user = userEvent.setup();
    render(<Editor initial={sampleDocumentLines} />);
    screen.getByRole("textbox", { name: "Description, line 1" }).focus();
    await user.keyboard("{Control>}d{/Control}");
    expect(state().map((row) => row[1])).toEqual([
      "Kitchen cabinets — install",
      "Kitchen cabinets — install",
      "Hardware",
    ]);
    expect(new Set(state().map((row) => row[0])).size).toBe(3);
    expect(screen.getByRole("textbox", { name: "Description, line 2" })).toHaveFocus();
    expect(screen.getByText("Line 1 duplicated")).toBeInTheDocument();
  });

  it("Ctrl+Backspace deletes the line; Undo in the toast puts it back", async () => {
    const user = userEvent.setup();
    render(<Editor initial={sampleDocumentLines} />);
    screen.getByRole("textbox", { name: "Description, line 1" }).focus();
    await user.keyboard("{Control>}{Backspace}{/Control}");
    expect(state().map((row) => row[0])).toEqual(["d2"]);
    expect(await screen.findByText("Line 1 deleted")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(state().map((row) => row[0])).toEqual(["d1", "d2"]));
  });

  it("keeps the last line (Ctrl+Backspace on a single line does nothing)", async () => {
    const user = userEvent.setup();
    render(<Editor initial={[sampleDocumentLines[0]!]} />);
    screen.getByRole("textbox", { name: "Description, line 1" }).focus();
    await user.keyboard("{Control>}{Backspace}{/Control}");
    expect(state()).toHaveLength(1);
  });

  it("Enter on the last line adds a line; typing fills it", async () => {
    const user = userEvent.setup();
    render(<Editor initial={sampleDocumentLines} />);
    const qty = screen.getByRole("textbox", { name: "Qty, line 2" });
    await user.click(qty);
    await user.keyboard("{Enter}");
    expect(state()).toHaveLength(3);
    await user.keyboard("{Control>}a{/Control}3");
    expect(state()[2]![2]).toBe("3");
  });

  it("is axe-clean", async () => {
    const { container } = render(<Editor initial={sampleDocumentLines} />);
    await expectNoAxeViolations(container);
  });
});

describe("parseLineDiscount", () => {
  it.each([
    ["", { type: "none", value: "0" }],
    ["10%", { type: "percent", value: "10" }],
    [" 12,5 % ", { type: "percent", value: "12.5" }],
    ["5", { type: "amount", value: "5" }],
    ["$5.00", { type: "amount", value: "5.00" }],
  ])("%s", (text, expected) => {
    expect(parseLineDiscount(text)).toEqual(expected);
  });

  it.each(["abc", "101%", "-5", "1.23456"])("refuses %s", (text) => {
    expect(parseLineDiscount(text)).toBeNull();
  });
});
