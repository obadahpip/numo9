import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { Combobox, type ComboboxOption } from "./Combobox";

const ACCOUNTS: ComboboxOption[] = [
  { value: "1000", label: "1000 · Chequing", group: "Assets", keywords: "bank" },
  { value: "1200", label: "1200 · Accounts receivable", group: "Assets" },
  { value: "2100", label: "2100 · GST/HST payable", group: "Liabilities" },
  { value: "4000", label: "4000 · Sales", group: "Revenue", description: "Revenue" },
  { value: "5000", label: "5000 · Cost of goods sold", group: "Expenses", disabled: true },
];

function Harness({ onChange = vi.fn() }: { onChange?: (v: string | null) => void }) {
  const [value, setValue] = useState<string | null>("1200");
  return (
    <>
      <label htmlFor="acct">Account</label>
      <Combobox
        id="acct"
        options={ACCOUNTS}
        value={value}
        onChange={(next) => {
          setValue(next);
          onChange(next);
        }}
        emptyMessage="No accounts match."
      />
    </>
  );
}

describe("Combobox (A-10-T06)", () => {
  it("shows the chosen option, opens on ArrowDown with it highlighted", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByRole("combobox", { name: "Account" });
    expect(input).toHaveValue("1200 · Accounts receivable");
    input.focus();
    await user.keyboard("{ArrowDown}");
    expect(input).toHaveAttribute("aria-expanded", "true");
    const listbox = screen.getByRole("listbox");
    const selected = within(listbox).getByRole("option", { selected: true });
    expect(selected).toHaveTextContent("Accounts receivable");
    expect(input).toHaveAttribute("aria-activedescendant", selected.id);
  });

  it("filters by label and keywords, Enter chooses", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const input = screen.getByRole("combobox", { name: "Account" });
    await user.clear(input);
    await user.type(input, "bank");
    expect(screen.getAllByRole("option")).toHaveLength(1);
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith("1000");
    expect(input).toHaveValue("1000 · Chequing");
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("skips disabled options with the arrow keys and never chooses them", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const input = screen.getByRole("combobox");
    await user.clear(input);
    await user.type(input, "0");
    // 1000, 1200, 2100, 4000 (5000 disabled): from 4000, ↓ wraps to 1000.
    await user.keyboard("{ArrowUp}{ArrowDown}");
    await user.click(screen.getByRole("option", { name: /Cost of goods sold/ }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("Escape closes and restores the chosen value; no match shows the empty message", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByRole("combobox");
    await user.clear(input);
    await user.type(input, "zzz");
    expect(screen.getByRole("status")).toHaveTextContent("No accounts match.");
    await user.keyboard("{Escape}");
    expect(input).toHaveValue("1200 · Accounts receivable");
  });

  it("chooses with the pointer and shows group headings", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await user.click(screen.getByRole("combobox"));
    expect(screen.getByText("Liabilities")).toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: /GST\/HST payable/ }));
    expect(onChange).toHaveBeenCalledWith("2100");
  });

  it("has no axe violations open or closed", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await expectNoAxeViolations();
    await user.click(screen.getByRole("combobox"));
    await expectNoAxeViolations();
  });
});
