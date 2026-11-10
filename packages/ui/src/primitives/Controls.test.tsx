import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { Checkbox } from "./Checkbox";
import { Input } from "./Input";
import { RadioGroup } from "./Radio";
import { Select } from "./Select";
import { Switch } from "./Switch";
import { Tabs } from "./Tabs";

describe("Input (A-10-T06)", () => {
  it("marks invalid state and renders prefix/suffix decoratively", async () => {
    render(
      <label>
        Amount
        <Input invalid prefix="$" suffix="CAD" numeric defaultValue="1,234.56" />
      </label>,
    );
    const input = screen.getByRole("textbox", { name: "Amount" });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.className).toContain("text-end");
    await expectNoAxeViolations();
  });
});

describe("Checkbox, RadioGroup, Switch (A-10-T06)", () => {
  it("Checkbox toggles with Space and is labelled", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Checkbox label="Include archived" onCheckedChange={onChange} />);
    const box = screen.getByRole("checkbox", { name: "Include archived" });
    box.focus();
    await user.keyboard(" ");
    expect(onChange).toHaveBeenCalledWith(true);
    expect(box).toHaveAttribute("aria-checked", "true");
  });

  it("Checkbox supports indeterminate (select-all)", () => {
    render(<Checkbox aria-label="Select all rows" checked="indeterminate" />);
    expect(screen.getByRole("checkbox", { name: "Select all rows" })).toHaveAttribute(
      "aria-checked",
      "mixed",
    );
  });

  it("RadioGroup moves and selects with the arrow keys", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <RadioGroup
        aria-label="Book"
        defaultValue="both"
        onValueChange={onChange}
        options={[
          { value: "both", label: "Both books" },
          { value: "accounting", label: "Accounting book only" },
          { value: "tax", label: "Tax book only", description: "Used for CRA adjustments" },
        ]}
      />,
    );
    const group = screen.getByRole("radiogroup", { name: "Book" });
    const radios = within(group).getAllByRole("radio");
    await user.click(radios[0]!);
    // Hold the key: Radix selects on the focus that the arrow key moves (after a tick).
    await user.keyboard("{ArrowDown>}");
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith("accounting"));
    await user.keyboard("{/ArrowDown}");
    expect(radios[1]).toHaveFocus();
    expect(radios[2]).toHaveAccessibleDescription("Used for CRA adjustments");
  });

  it("Switch toggles", async () => {
    const user = userEvent.setup();
    render(<Switch label="Compact density" />);
    const control = screen.getByRole("switch", { name: "Compact density" });
    await user.click(control);
    expect(control).toHaveAttribute("aria-checked", "true");
  });

  it("have no axe violations", async () => {
    render(
      <div>
        <Checkbox label="Send a copy to me" description="To your sign-in email" />
        <RadioGroup
          aria-label="Time format"
          defaultValue="12h"
          options={[
            { value: "12h", label: "12-hour (1:30 p.m.)" },
            { value: "24h", label: "24-hour (13:30)" },
          ]}
        />
        <Switch label="Compact density" description="Shows more rows" />
      </div>,
    );
    await expectNoAxeViolations();
  });
});

describe("Select (A-10-T06)", () => {
  function Province() {
    const [value, setValue] = useState<string>();
    return (
      <>
        <span id="prov">Province</span>
        <Select
          aria-labelledby="prov"
          placeholder="Choose a province"
          value={value}
          onValueChange={setValue}
          options={[
            { value: "AB", label: "Alberta" },
            { value: "BC", label: "British Columbia" },
            { value: "ON", label: "Ontario" },
          ]}
        />
        <output>{value}</output>
      </>
    );
  }

  it("opens with the keyboard and selects", async () => {
    const user = userEvent.setup();
    render(<Province />);
    const trigger = screen.getByRole("combobox", { name: "Province" });
    expect(trigger).toHaveTextContent("Choose a province");
    trigger.focus();
    await user.keyboard("{Enter}");
    const listbox = await screen.findByRole("listbox");
    expect(within(listbox).getAllByRole("option")).toHaveLength(3);
    await user.click(within(listbox).getByRole("option", { name: "Ontario" }));
    expect(screen.getByRole("status")).toHaveTextContent("ON");
    expect(trigger).toHaveTextContent("Ontario");
  });

  it("has no axe violations (closed)", async () => {
    render(<Province />);
    await expectNoAxeViolations();
  });
});

describe("Tabs (A-10-T06)", () => {
  it("switches panels with the arrow keys and labels panels by their tab", async () => {
    const user = userEvent.setup();
    render(
      <Tabs
        label="Contact roles"
        items={[
          { value: "all", label: "All contacts", count: 120, content: <p>All list</p> },
          { value: "customers", label: "Customers", count: 80, content: <p>Customer list</p> },
          { value: "suppliers", label: "Suppliers", count: 40, content: <p>Supplier list</p> },
        ]}
      />,
    );
    const tabs = screen.getAllByRole("tab");
    tabs[0]!.focus();
    await user.keyboard("{ArrowRight}");
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Customer list");
    expect(screen.getByRole("tablist", { name: "Contact roles" })).toBeInTheDocument();
    await expectNoAxeViolations();
  });
});
