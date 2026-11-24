import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { chartAccounts, sampleTaxCodes } from "../pickers/fixtures";
import { ToastProvider } from "../primitives/Toast";
import { DocumentLines, newDocumentLine, type DocumentGridLine } from "./DocumentLines";
import { documentLabels } from "./fixtures";

/**
 * F-01-T10 — bank mode of the document grid (spend / receive money): a line is a description,
 * an account, a tax code and an amount; no item, quantity or discount; the side still filters the
 * accounts and tax codes (purchase codes only on spend).
 */
function Editor({ side }: { side: "sales" | "purchase" }) {
  const [lines, setLines] = useState<DocumentGridLine[]>([{ ...newDocumentLine(), id: "b1" }]);
  return (
    <ToastProvider labels={{ region: "Notifications", close: "Close" }}>
      <DocumentLines
        bank
        lines={lines}
        onChange={setLines}
        side={side}
        date="2026-07-15"
        accounts={chartAccounts}
        taxCodes={sampleTaxCodes}
        amounts={{ b1: { tax: "13.00", amount: "113.00" } }}
        labels={documentLabels}
        locale="en-CA"
      />
      <output data-testid="state">{JSON.stringify(lines)}</output>
    </ToastProvider>
  );
}

it("shows only Description · Amount · Account · Tax code · Tax amount", () => {
  render(<Editor side="purchase" />);
  const grid = screen.getByRole("grid");
  const headers = within(grid)
    .getAllByRole("columnheader")
    .map((h) => h.textContent)
    .filter(Boolean);
  expect(headers).toEqual([
    "#",
    "Description",
    "Amount",
    "Account",
    "Tax code",
    "Tax amount",
    "Actions",
  ]);
  expect(screen.queryByRole("textbox", { name: /Qty/ })).toBeNull();
  // The column chooser has nothing to offer for the dropped columns.
  expect(screen.queryByRole("checkbox", { name: "Item" })).toBeNull();
});

it("the amount typed is the line's unit price (quantity 1)", async () => {
  render(<Editor side="purchase" />);
  const amount = screen.getByRole("textbox", { name: "Amount, line 1" });
  await userEvent.type(amount, "113");
  await userEvent.tab();
  const [line] = JSON.parse(screen.getByTestId("state").textContent ?? "[]") as DocumentGridLine[];
  expect(Number(line?.unitPrice)).toBe(113);
  expect(line?.quantity).toBe("1");
});

it("spend lines offer purchase tax codes only; receive lines sales codes only", async () => {
  const { unmount } = render(<Editor side="purchase" />);
  await userEvent.click(screen.getByRole("combobox", { name: "Tax code, line 1" }));
  const purchase = screen.getAllByRole("option").map((o) => o.textContent ?? "");
  expect(purchase.length).toBeGreaterThan(0);
  const purchaseIds = new Set(
    sampleTaxCodes.filter((c) => c.side === "purchase").map((c) => c.name),
  );
  expect(purchase.every((text) => [...purchaseIds].some((name) => text.includes(name)))).toBe(true);
  unmount();
  render(<Editor side="sales" />);
  await userEvent.click(screen.getByRole("combobox", { name: "Tax code, line 1" }));
  const salesNames = sampleTaxCodes.filter((c) => c.side === "sales").map((c) => c.name);
  const sales = screen.getAllByRole("option").map((o) => o.textContent ?? "");
  expect(sales.every((text) => salesNames.some((name) => text.includes(name)))).toBe(true);
});
