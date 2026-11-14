import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { expectNoAxeViolations } from "../test/axe";
import contextRules from "./account-contexts.json";
import {
  AccountPicker,
  allowedInContext,
  type AccountContext,
  type AccountType,
} from "./AccountPicker";
import { chartAccounts, typeLabels } from "./fixtures";

/** C-01-T10 — shared account picker: context filtering, grouping, sub-accounts, search. */
function Harness({
  context,
  types,
  initial = null,
}: {
  context?: AccountContext;
  types?: AccountType[];
  initial?: string | null;
}) {
  const [value, setValue] = useState<string | null>(initial);
  return (
    <>
      <label htmlFor="acc">Account</label>
      <AccountPicker
        id="acc"
        accounts={chartAccounts}
        value={value}
        onChange={setValue}
        context={context}
        types={types}
        typeLabels={typeLabels}
        emptyMessage="No accounts match."
      />
      <output>{value ?? "none"}</output>
    </>
  );
}

async function openList(): Promise<string[]> {
  const user = userEvent.setup();
  await user.click(screen.getByRole("combobox", { name: "Account" }));
  return screen.getAllByRole("option").map((option) => option.textContent ?? "");
}

describe("AccountPicker contexts (C-01-T10)", () => {
  it("sales context hides expense accounts (gap-07 groundwork)", async () => {
    render(<Harness context="sales" />);
    const labels = await openList();
    expect(labels).toEqual([
      "2300 · Customer deposits",
      "4000 · Sales",
      "4001 · Sales — retail",
      "4002 · Sales — wholesale",
      "4500 · Interest income",
    ]);
    expect(labels.some((label) => /^6/.test(label))).toBe(false);
    expect(screen.queryByText("Expenses")).not.toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
  });

  it("purchase context: expenses and assets a bill buys; no engine or bank accounts", async () => {
    render(<Harness context="purchase" />);
    const codes = (await openList()).map((label) => label.slice(0, 4));
    expect(codes).toEqual(["1200", "1630", "6080", "6210", "6211", "6300"]);
  });

  it("bank context offers bank accounts only, journal everything but current year earnings", async () => {
    const { unmount } = render(<Harness context="bank" />);
    expect((await openList()).map((l) => l.slice(0, 4))).toEqual(["1010", "2400"]);
    unmount();
    render(<Harness context="journal" />);
    const codes = (await openList()).map((l) => l.slice(0, 4));
    expect(codes).toContain("1100");
    expect(codes).toContain("2100");
    expect(codes).not.toContain("3210");
    expect(codes).not.toContain("6900"); // archived
  });

  it("parents are shown under their type but can't be chosen; sub-accounts are indented", async () => {
    const user = userEvent.setup();
    render(<Harness context="sales" />);
    await openList();
    const parent = screen.getByRole("option", { name: "4000 · Sales" });
    expect(parent).toHaveAttribute("aria-disabled", "true");
    const child = screen.getByRole("option", { name: "4001 · Sales — retail" });
    expect(child.style.paddingInlineStart).not.toBe("");
    await user.click(parent);
    expect(screen.getByRole("status")).toHaveTextContent("none");
    await user.click(child);
    expect(screen.getByRole("status")).toHaveTextContent("c4001");
  });

  it("a parent disappears when none of its sub-accounts is offered", async () => {
    render(<Harness context="sales" types={["expense"]} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "Account" }));
    expect(screen.queryAllByRole("option")).toHaveLength(0);
    expect(screen.getByText("No accounts match.")).toBeInTheDocument();
  });

  it("searches by code or name inside the context", async () => {
    const user = userEvent.setup();
    render(<Harness context="purchase" />);
    const input = screen.getByRole("combobox", { name: "Account" });
    await user.type(input, "fuel");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["6211 · Fuel"]);
    await user.keyboard("{Enter}");
    expect(screen.getByRole("status")).toHaveTextContent("c6211");
    await user.clear(input);
    await user.type(input, "4000");
    expect(screen.getByText("No accounts match.")).toBeInTheDocument(); // revenue: not here
    await expectNoAxeViolations();
  });

  it("keeps showing the current value even when the context would not offer it", () => {
    render(<Harness context="sales" initial="c6080" />);
    expect(screen.getByRole("combobox", { name: "Account" })).toHaveValue("6080 · Office supplies");
  });

  it("rules match the shared JSON the server checks against", () => {
    expect(Object.keys(contextRules.contexts).sort()).toEqual(
      ["bank", "journal", "purchase", "sales"].sort(),
    );
    const card = chartAccounts.find((a) => a.code === "2400")!;
    expect(allowedInContext(card, "bank")).toBe(true);
    expect(allowedInContext(card, "sales")).toBe(false);
    const ar = chartAccounts.find((a) => a.code === "1100")!;
    expect(allowedInContext(ar, "sales")).toBe(false);
    expect(allowedInContext(ar, "journal")).toBe(true);
  });
});
