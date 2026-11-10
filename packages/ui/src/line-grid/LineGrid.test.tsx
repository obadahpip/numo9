import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { sampleAccounts } from "../pickers/fixtures";
import { expectNoAxeViolations } from "../test/axe";
import { journalLabels, sampleJournal } from "./fixtures";
import { journalBalance, JournalLines, type JournalLine } from "./JournalLines";
import { LineGrid, type DocumentLine, type LineColumn } from "./LineGrid";

let n = 0;
const blank = (): DocumentLine => ({ id: `new-${++n}`, item: "", amount: null });
const COLUMNS: LineColumn[] = [
  { id: "item", header: "Item", kind: "text" },
  { id: "note", header: "Note", kind: "text", optional: true },
  { id: "amount", header: "Amount", kind: "money", total: true },
];

function Lines({ initial }: { initial: DocumentLine[] }) {
  const [lines, setLines] = useState(initial);
  return (
    <>
      <LineGrid
        lines={lines}
        onChange={setLines}
        columns={COLUMNS}
        newLine={blank}
        labels={journalLabels}
        locale="en-CA"
        defaultHiddenColumns={["note"]}
      />
      <output data-testid="state">
        {JSON.stringify(lines.map((l) => [l.id, l.item, l.amount]))}
      </output>
    </>
  );
}

const state = () =>
  JSON.parse(screen.getByTestId("state").textContent ?? "[]") as [string, string, string | null][];

const THREE: DocumentLine[] = [
  { id: "a", item: "Desk", amount: "100.00" },
  { id: "b", item: "Chair", amount: "50.25" },
  { id: "c", item: "Lamp", amount: null },
];

describe("LineGrid (A-10-T11)", () => {
  it("↑/↓ move between lines in the same column; Enter moves down", async () => {
    const user = userEvent.setup();
    render(<Lines initial={THREE} />);
    screen.getByRole("textbox", { name: "Item, line 1" }).focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("textbox", { name: "Item, line 2" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("textbox", { name: "Item, line 3" })).toHaveFocus();
    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(screen.getByRole("textbox", { name: "Item, line 1" })).toHaveFocus();
  });

  it("Enter on the last line adds a line and focuses the same column; the money value is kept", async () => {
    const user = userEvent.setup();
    render(<Lines initial={THREE} />);
    const amount = screen.getByRole("textbox", { name: "Amount, line 3" });
    await user.click(amount);
    await user.type(amount, "1,234.5{Enter}");
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Amount, line 4" })).toHaveFocus(),
    );
    expect(state()[2]).toEqual(["c", "Lamp", "1234.50"]);
    expect(state()).toHaveLength(4);
  });

  it("totals money columns exactly, in the locale format", async () => {
    const user = userEvent.setup();
    render(<Lines initial={THREE} />);
    const totals = screen.getByRole("row", { name: /Totals/ });
    expect(totals).toHaveTextContent("$150.25");
    const amount = screen.getByRole("textbox", { name: "Amount, line 3" });
    await user.type(amount, "0.10");
    await user.tab();
    expect(totals).toHaveTextContent("$150.35");
  });

  it("Add a line and Delete line; minimum lines can't be deleted", async () => {
    const user = userEvent.setup();
    render(<Lines initial={THREE.slice(0, 1)} />);
    expect(screen.getByRole("button", { name: "Delete line 1" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Add a line" }));
    expect(screen.getByRole("textbox", { name: "Item, line 2" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Delete line 1" }));
    expect(state().map((s) => s[0])).toEqual([expect.stringMatching(/^new-/)]);
  });

  it("Alt+Shift+↑/↓ moves a line (keyboard reorder) and announces it", async () => {
    const user = userEvent.setup();
    render(<Lines initial={THREE} />);
    screen.getByRole("textbox", { name: "Item, line 1" }).focus();
    await user.keyboard("{Alt>}{Shift>}{ArrowDown}{/Shift}{/Alt}");
    expect(state().map((s) => s[0])).toEqual(["b", "a", "c"]);
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Item, line 2" })).toHaveFocus(),
    );
    expect(screen.getByText("Line 1 moved to position 2")).toHaveAttribute("role", "status");
  });

  it("drag handle reorders lines with the mouse (HTML drag and drop)", () => {
    render(<Lines initial={THREE} />);
    const handle = screen.getByRole("button", { name: /Move line 3/ });
    const firstRow = screen.getByRole("textbox", { name: "Item, line 1" }).closest("tr")!;
    const dataTransfer = { setData: () => undefined, effectAllowed: "", dropEffect: "" };
    fireEvent.dragStart(handle, { dataTransfer });
    fireEvent.dragOver(firstRow, { dataTransfer });
    fireEvent.drop(firstRow, { dataTransfer });
    expect(state().map((s) => s[0])).toEqual(["c", "a", "b"]);
  });

  it("column chooser shows optional columns", async () => {
    const user = userEvent.setup();
    render(<Lines initial={THREE} />);
    expect(screen.queryByRole("columnheader", { name: "Note" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Columns" }));
    expect(screen.getByRole("checkbox", { name: "Item" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: "Note" }));
    expect(screen.getByRole("columnheader", { name: "Note" })).toBeInTheDocument();
  });

  it("unreadable amounts are flagged, not guessed", async () => {
    const user = userEvent.setup();
    render(<Lines initial={THREE} />);
    const amount = screen.getByRole("textbox", { name: "Amount, line 3" });
    await user.type(amount, "12.345");
    await user.tab();
    expect(amount).toHaveAttribute("aria-invalid", "true");
    expect(state()[2]?.[2]).toBeNull();
  });

  it("has no axe violations", async () => {
    render(<Lines initial={THREE} />);
    await expectNoAxeViolations();
  });
});

describe("JournalLines — the journal uses LineGrid (A-10-T11)", () => {
  function Journal({ initial = sampleJournal }: { initial?: JournalLine[] }) {
    const [lines, setLines] = useState(initial);
    return (
      <>
        <JournalLines
          lines={lines}
          onChange={setLines}
          accounts={sampleAccounts}
          labels={journalLabels}
          locale="en-CA"
        />
        <output data-testid="journal">{JSON.stringify(lines)}</output>
      </>
    );
  }
  const journal = () =>
    JSON.parse(screen.getByTestId("journal").textContent ?? "[]") as JournalLine[];

  it("names both totals and the difference until it balances (microcopy §3.5)", async () => {
    const user = userEvent.setup();
    render(<Journal />);
    const indicator = screen.getAllByRole("status").find((s) => s.hasAttribute("data-balanced"))!;
    expect(indicator).toHaveTextContent(
      "Debits ($1,250.00) and credits ($1,200.00) differ by $50.00. Adjust a line so the difference is $0.00.",
    );
    expect(indicator).toHaveAttribute("data-balanced", "false");

    const credit = screen.getByRole("textbox", { name: "Credit, line 2" });
    await user.clear(credit);
    await user.type(credit, "1250");
    await user.tab();
    expect(indicator).toHaveTextContent("Balanced — debits equal credits.");
    expect(indicator).toHaveAttribute("data-balanced", "true");
  });

  it("a line holds a debit or a credit: entering one clears the other", async () => {
    const user = userEvent.setup();
    render(<Journal />);
    const credit1 = screen.getByRole("textbox", { name: "Credit, line 1" });
    await user.type(credit1, "10");
    await user.tab();
    expect(journal()[0]).toMatchObject({ debit: null, credit: "10.00" });
  });

  it("account cells are account pickers; ↓ with the list closed moves to the next line", async () => {
    const user = userEvent.setup();
    render(<Journal />);
    const account1 = screen.getByRole("combobox", { name: "Account, line 1" });
    expect(account1).toHaveValue("1000 · Chequing");
    account1.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("combobox", { name: "Account, line 2" })).toHaveFocus();

    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");
    const listbox = await screen.findByRole("listbox");
    expect(within(listbox).getAllByRole("option").length).toBeGreaterThan(3);
    await user.keyboard("{Escape}");
  });

  it("journalBalance: empty journals don't balance", () => {
    expect(journalBalance([], { debit: "0.00", credit: "0.00" }).balanced).toBe(false);
  });

  it("has no axe violations", async () => {
    render(<Journal />);
    await expectNoAxeViolations();
  });
});
