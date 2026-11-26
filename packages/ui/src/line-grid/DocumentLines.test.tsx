import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { chartAccounts, sampleTaxCodes } from "../pickers/fixtures";
import { ToastProvider } from "../primitives/Toast";
import { expectNoAxeViolations } from "../test/axe";
import {
  DocumentLines,
  parseLineDiscount,
  pasteRows,
  type DocumentGridLine,
} from "./DocumentLines";
import { documentLabels, roughAmounts, sampleDocumentLines } from "./fixtures";
import { localColumnStore, type ColumnStore } from "./LineGrid";

const RATES = Object.fromEntries(sampleTaxCodes.map((c) => [c.id, c.rate ?? "0"]));

function Editor({
  initial,
  columnStore,
}: {
  initial: DocumentGridLine[];
  columnStore?: ColumnStore;
}) {
  const [lines, setLines] = useState(initial);
  return (
    <ToastProvider labels={{ region: "Notifications", close: "Close" }}>
      <DocumentLines
        lines={lines}
        onChange={setLines}
        side="sales"
        date="2026-07-15"
        accounts={chartAccounts}
        taxCodes={sampleTaxCodes}
        amounts={roughAmounts(lines, RATES)}
        taxWhy={{ d1: "Ontario customer → HST 13 %" }}
        columnStore={columnStore}
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
    expect(screen.getByRole("status", { name: /^Amount, line 2$/ })).toHaveTextContent("$280.80");
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

  it("sales lines offer no expense accounts and no purchase codes (gap-07)", async () => {
    const user = userEvent.setup();
    render(<Editor initial={sampleDocumentLines} />);
    await user.click(screen.getByRole("combobox", { name: "Account, line 1" }));
    await user.keyboard("{Control>}a{/Control}{Backspace}");
    const accounts = screen.getAllByRole("option").map((o) => o.textContent ?? "");
    expect(accounts.some((t) => t.includes("Sales — retail"))).toBe(true);
    expect(accounts.some((t) => t.includes("Interest income"))).toBe(true);
    for (const banned of ["Office supplies", "Fuel", "Chequing", "Accounts receivable"]) {
      expect(accounts.some((t) => t.includes(banned))).toBe(false);
    }
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("combobox", { name: "Tax code, line 1" }));
    await user.keyboard("{Control>}a{/Control}{Backspace}");
    const codes = screen.getAllByRole("option").map((o) => o.textContent ?? "");
    expect(codes.some((t) => t.includes("HST 13 % (Ontario) on sales"))).toBe(true);
    expect(codes.some((t) => t.includes("on purchases"))).toBe(false);
    // MB RST 8 % ended 30 Jun 2019: not offered on a 2026 document.
    expect(codes.some((t) => t.includes("Manitoba"))).toBe(false);
  });

  it("explains why a line has its tax code", () => {
    render(<Editor initial={sampleDocumentLines} />);
    const why = screen.getByRole("button", { name: "Why this tax code, line 1" });
    expect(why).toHaveAccessibleDescription("Ontario customer → HST 13 %");
    expect(screen.queryByRole("button", { name: "Why this tax code, line 2" })).toBeNull();
  });

  it("is axe-clean", async () => {
    const { container } = render(<Editor initial={sampleDocumentLines} />);
    await expectNoAxeViolations(container);
  });
});

describe("column choice (D-01-T13)", () => {
  beforeEach(() => localStorage.clear());

  it("persists per user and grid, and survives a new session", async () => {
    const user = userEvent.setup();
    const store = localColumnStore("numo9.lines.u1.sales");
    const { unmount } = render(<Editor initial={sampleDocumentLines} columnStore={store} />);
    await user.click(screen.getByRole("button", { name: "Columns" }));
    await user.click(screen.getByRole("checkbox", { name: "Discount" }));
    await user.keyboard("{Escape}");
    expect(screen.getByRole("columnheader", { name: "Discount" })).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("numo9.lines.u1.sales")!)).toEqual(["item"]);
    unmount();
    render(
      <Editor
        initial={sampleDocumentLines}
        columnStore={localColumnStore("numo9.lines.u1.sales")}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "Discount" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Item" })).toBeNull();
  });

  it("another user keeps the defaults; unreadable storage falls back to them", () => {
    localStorage.setItem("numo9.lines.u1.sales", JSON.stringify([]));
    localStorage.setItem("numo9.lines.u2.sales", "{oops");
    render(
      <Editor
        initial={sampleDocumentLines}
        columnStore={localColumnStore("numo9.lines.u2.sales")}
      />,
    );
    expect(screen.queryByRole("columnheader", { name: "Discount" })).toBeNull();
  });

  it("notes hidden columns that hold values and shows them on request", async () => {
    const user = userEvent.setup();
    render(<Editor initial={sampleDocumentLines} />);
    expect(screen.getByText("Hidden columns with values: Item, Discount.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show" }));
    expect(screen.getByRole("columnheader", { name: "Discount" })).toBeInTheDocument();
    expect(screen.queryByText(/Hidden columns with values/)).toBeNull();
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

describe("paste from a spreadsheet (D-01-T15)", () => {
  const rows = (n: number) =>
    Array.from({ length: n }, (_, i) =>
      [
        `Item ${i + 1}`,
        String(i + 1),
        `$${(i + 1) * 10}.50`,
        "4001",
        "HST 13 % (Ontario) on sales",
      ].join("\t"),
    ).join("\r\n");

  it("20 rows pasted into Description become 20 lines", () => {
    render(<Editor initial={[{ ...sampleDocumentLines[0]!, id: "only", description: "" }]} />);
    const cell = screen.getByRole("textbox", { name: "Description, line 1" });
    fireEvent.paste(cell, { clipboardData: { getData: () => `${rows(20)}\r\n` } });
    const lines = state();
    expect(lines).toHaveLength(20);
    expect(lines[19]).toEqual([expect.any(String), "Item 20", "20"]);
    expect(screen.getByRole("textbox", { name: "Unit price, line 20" })).toHaveValue("200.50");
    expect(document.querySelectorAll("td[data-invalid]")).toHaveLength(0);
  });

  it("flags the cells that don't fit, and unflags one once edited", async () => {
    const user = userEvent.setup();
    render(<Editor initial={[{ ...sampleDocumentLines[0]!, id: "only", description: "" }]} />);
    const text = [
      "Good\t2\t10.00\t4001\tsales.ON.standard",
      "Bad qty\tlots\t10.00\tOffice supplies\tHST 13 % (Ontario) on purchases",
      "Bad price\t1\tten\t9999\tExempt on sales",
    ].join("\n");
    fireEvent.paste(screen.getByRole("textbox", { name: "Description, line 1" }), {
      clipboardData: { getData: () => text },
    });
    expect(state()).toHaveLength(3);
    const flagged = [...document.querySelectorAll("tr[data-line]")].map(
      (row) => [...row.querySelectorAll("td[data-invalid]")].length,
    );
    // line 2: quantity, account (expense on a sales line), tax code (purchase); line 3: price, account
    expect(flagged).toEqual([0, 3, 2]);
    expect(screen.getByRole("textbox", { name: "Qty, line 2" })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    await user.clear(screen.getByRole("textbox", { name: "Qty, line 2" }));
    await user.type(screen.getByRole("textbox", { name: "Qty, line 2" }), "3");
    expect(screen.getByRole("textbox", { name: "Qty, line 2" })).not.toHaveAttribute(
      "aria-invalid",
    );
  });

  it("a plain paste into one cell is left to the browser", () => {
    render(<Editor initial={sampleDocumentLines} />);
    fireEvent.paste(screen.getByRole("textbox", { name: "Description, line 1" }), {
      clipboardData: { getData: () => "just text\n" },
    });
    expect(state()).toHaveLength(2);
  });
});

describe("DocumentLines extra columns (D-02-T12)", () => {
  function Quote() {
    const [lines, setLines] = useState<DocumentGridLine[]>(sampleDocumentLines);
    return (
      <ToastProvider labels={{ region: "Notifications", close: "Close" }}>
        <DocumentLines
          lines={lines}
          onChange={setLines}
          side="sales"
          date="2026-07-15"
          accounts={chartAccounts}
          taxCodes={sampleTaxCodes}
          labels={documentLabels}
          locale="en-CA"
          extraColumns={[
            {
              id: "isOptional",
              header: "Optional",
              kind: "custom",
              width: 80,
              render: ({ id, label, value, onChange }) => (
                <input
                  id={id}
                  type="checkbox"
                  aria-label={label}
                  checked={Boolean(value)}
                  onChange={(event) => onChange(event.target.checked)}
                />
              ),
            },
          ]}
        />
        <output data-testid="optional">
          {JSON.stringify(lines.map((l) => Boolean(l.isOptional)))}
        </output>
      </ToastProvider>
    );
  }

  it("adds the document's columns before the calculated ones and keeps their values", async () => {
    const user = userEvent.setup();
    render(<Quote />);
    const headers = within(screen.getByRole("grid", { name: "Invoice lines" }))
      .getAllByRole("columnheader")
      .map((h) => h.textContent)
      .filter(Boolean);
    expect(headers.slice(4, 8)).toEqual(["Account", "Tax code", "Optional", "Tax amount"]);
    await user.click(screen.getByRole("checkbox", { name: "Optional, line 2" }));
    expect(screen.getByTestId("optional")).toHaveTextContent("[false,true]");
  });
});

describe("pasteRows", () => {
  it("starts at the pasted line and column, overwriting then adding", () => {
    const pasted = pasteRows(
      [
        ["7", "12"],
        ["8", "x"],
      ],
      1,
      ["quantity", "unitPrice"],
      sampleDocumentLines,
      {
        side: "sales",
        date: "2026-07-15",
        accounts: chartAccounts,
        taxCodes: sampleTaxCodes,
        locale: "en-CA",
      },
    );
    expect(pasted.lines.map((l) => [l.quantity, l.unitPrice])).toEqual([
      ["1", "4800.00"],
      ["7", "12.0000"],
      ["8", null],
    ]);
    expect(Object.values(pasted.invalid)).toEqual([["unitPrice"]]);
  });
});
