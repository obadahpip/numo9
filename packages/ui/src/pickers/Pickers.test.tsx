import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import type { IsoDate } from "../format/dates";
import type { AppLocale } from "../format/locale";
import { expectNoAxeViolations } from "../test/axe";
import { AccountPicker, type AccountType } from "./AccountPicker";
import { ContactPicker } from "./ContactPicker";
import { CurrencyInput } from "./CurrencyInput";
import { DatePicker } from "./DatePicker";
import { dateLabels, sampleAccounts, sampleContacts, typeLabels } from "./fixtures";
import { formatPostalCode, isValidPostalCode, postalCodeMatchesProvince } from "./postalCode";
import { PostalCodeInput } from "./PostalCodeInput";
import { ProvincePicker } from "./ProvincePicker";

const TODAY = "2026-10-15";

function DateHarness({
  initial = "2026-10-26",
  locale = "en-CA",
  onChange = vi.fn(),
  base,
}: {
  initial?: IsoDate | null;
  locale?: AppLocale;
  onChange?: (v: IsoDate | null) => void;
  base?: IsoDate;
}) {
  const [value, setValue] = useState<IsoDate | null>(initial);
  return (
    <>
      <label htmlFor="due">Due date</label>
      <DatePicker
        id="due"
        value={value}
        onChange={(next) => {
          setValue(next);
          onChange(next);
        }}
        locale={locale}
        today={TODAY}
        base={base}
        labels={dateLabels}
      />
      <output>{value ?? "none"}</output>
    </>
  );
}

describe("DatePicker (A-10-T09)", () => {
  it("shows the locale format and reads forgiving typed dates", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<DateHarness onChange={onChange} />);
    const input = screen.getByRole("textbox", { name: "Due date" });
    expect(input).toHaveValue("26 Oct 2026");
    await user.clear(input);
    await user.type(input, "+30{Enter}");
    expect(onChange).toHaveBeenLastCalledWith("2026-11-14");
    expect(input).toHaveValue("14 Nov 2026");
    await user.clear(input);
    await user.type(input, "31/12");
    await user.tab();
    expect(input).toHaveValue("31 Dec 2026");
  });

  it("French display", () => {
    render(<DateHarness locale="fr-CA" />);
    expect(screen.getByRole("textbox", { name: "Due date" })).toHaveValue("26 oct. 2026");
  });

  it("unreadable text keeps the old value and says what to type", async () => {
    const user = userEvent.setup();
    render(<DateHarness />);
    const input = screen.getByRole("textbox", { name: "Due date" });
    await user.clear(input);
    await user.type(input, "31/02/2026");
    await user.tab();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(dateLabels.unreadable);
    expect(screen.getByRole("status")).toHaveTextContent("2026-10-26");
  });

  it("calendar is keyboard-operable: Alt+↓ opens on the value, arrows/PageDown move, Enter chooses", async () => {
    const user = userEvent.setup();
    render(<DateHarness />);
    const input = screen.getByRole("textbox", { name: "Due date" });
    input.focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");
    const grid = await screen.findByRole("grid", { name: "October 2026" });
    await waitFor(() =>
      expect(within(grid).getByRole("button", { name: "26 Oct 2026" })).toHaveFocus(),
    );

    await user.keyboard("{ArrowRight}");
    await waitFor(() => expect(screen.getByRole("button", { name: "27 Oct 2026" })).toHaveFocus());
    await user.keyboard("{ArrowDown}");
    await waitFor(() => expect(screen.getByRole("button", { name: "3 Nov 2026" })).toHaveFocus());
    expect(screen.getByRole("grid", { name: "November 2026" })).toBeInTheDocument();
    await user.keyboard("{PageDown}");
    await waitFor(() => expect(screen.getByRole("button", { name: "3 Dec 2026" })).toHaveFocus());
    await user.keyboard("{Home}");
    await waitFor(() => expect(screen.getByRole("button", { name: "29 Nov 2026" })).toHaveFocus());
    await user.keyboard("{Enter}");
    expect(screen.getByRole("status")).toHaveTextContent("2026-11-29");
    await waitFor(() => expect(input).toHaveFocus());
  });

  it("Escape closes the calendar and returns focus to the input", async () => {
    const user = userEvent.setup();
    render(<DateHarness />);
    await user.click(screen.getByRole("button", { name: "Choose date" }));
    await screen.findByRole("grid");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("grid")).toBeNull());
    expect(screen.getByRole("textbox", { name: "Due date" })).toHaveFocus();
  });

  it("shortcuts count from the base date", async () => {
    const user = userEvent.setup();
    render(<DateHarness base="2026-10-01" />);
    await user.click(screen.getByRole("button", { name: "Choose date" }));
    await user.click(await screen.findByRole("button", { name: /In 14 days/ }));
    expect(screen.getByRole("status")).toHaveTextContent("2026-10-15");
    await user.click(screen.getByRole("button", { name: "Choose date" }));
    await user.click(await screen.findByRole("button", { name: /End of next month/ }));
    expect(screen.getByRole("status")).toHaveTextContent("2026-11-30");
  });

  it("clearing the text clears the value", async () => {
    const user = userEvent.setup();
    render(<DateHarness />);
    await user.clear(screen.getByRole("textbox", { name: "Due date" }));
    await user.tab();
    expect(screen.getByRole("status")).toHaveTextContent("none");
  });

  it("has no axe violations, closed and open", async () => {
    const user = userEvent.setup();
    render(<DateHarness />);
    await expectNoAxeViolations();
    await user.click(screen.getByRole("button", { name: "Choose date" }));
    await screen.findByRole("grid");
    await expectNoAxeViolations();
  });
});

describe("ProvincePicker (A-10-T09)", () => {
  it("lists 10 provinces and 3 territories in the user's language", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ProvincePicker
        aria-label="Province"
        locale="fr-CA"
        groupLabels={{ provinces: "Provinces", territories: "Territoires" }}
        onValueChange={onChange}
      />,
    );
    const trigger = screen.getByRole("combobox", { name: "Province" });
    trigger.focus();
    await user.keyboard("{Enter}");
    const listbox = await screen.findByRole("listbox");
    const names = within(listbox)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(names).toHaveLength(13);
    expect(names.slice(0, 3)).toEqual(["Alberta", "Colombie-Britannique", "Île-du-Prince-Édouard"]);
    await user.click(within(listbox).getByRole("option", { name: "Québec" }));
    expect(onChange).toHaveBeenCalledWith("QC");
  });

  it("has no axe violations", async () => {
    render(
      <ProvincePicker
        aria-label="Province"
        locale="en-CA"
        groupLabels={{ provinces: "Provinces", territories: "Territories" }}
        defaultValue="ON"
      />,
    );
    expect(screen.getByRole("combobox", { name: "Province" })).toHaveTextContent("Ontario");
    await expectNoAxeViolations();
  });
});

describe("Postal code (A-10-T09)", () => {
  it.each([
    ["m5v2t6", "M5V 2T6"],
    ["M5V 2T6", "M5V 2T6"],
    ["h2x-1y4", "H2X 1Y4"],
    ["k1a", "K1A"],
    ["k1a0b1extra", "K1A 0B1"],
  ])("formats %s → %s", (input, expected) => {
    expect(formatPostalCode(input)).toBe(expected);
  });

  it("validates the Canada Post pattern", () => {
    expect(isValidPostalCode("M5V 2T6")).toBe(true);
    expect(isValidPostalCode("m5v2t6")).toBe(true);
    expect(isValidPostalCode("M5V2T")).toBe(false);
    expect(isValidPostalCode("D5V 2T6")).toBe(false); // D never used
    expect(isValidPostalCode("W5V 2T6")).toBe(false); // W never first
    expect(isValidPostalCode("M5W 2T6")).toBe(true);
    expect(isValidPostalCode("12345")).toBe(false);
    expect(postalCodeMatchesProvince("M5V 2T6", "KLMNP")).toBe(true);
    expect(postalCodeMatchesProvince("H2X 1Y4", "KLMNP")).toBe(false);
  });

  it("upper-cases and inserts the space as you type", async () => {
    const user = userEvent.setup();
    function Harness() {
      const [value, setValue] = useState("");
      return <PostalCodeInput aria-label="Postal code" value={value} onChange={setValue} />;
    }
    render(<Harness />);
    const input = screen.getByRole("textbox", { name: "Postal code" });
    await user.type(input, "m5v2t6");
    expect(input).toHaveValue("M5V 2T6");
    await expectNoAxeViolations();
  });
});

describe("CurrencyInput (A-10-T09)", () => {
  function Harness({ locale = "en-CA" as AppLocale, onChange = vi.fn() }) {
    const [value, setValue] = useState<string | null>("1234.5");
    return (
      <>
        <label htmlFor="amt">Amount</label>
        <CurrencyInput
          id="amt"
          locale={locale}
          value={value}
          onChange={(next) => {
            setValue(next);
            onChange(next);
          }}
          unreadableMessage="Enter an amount like 1,234.56."
        />
      </>
    );
  }

  it("shows the amount for the locale and reads forgiving input", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const input = screen.getByRole("textbox", { name: "Amount" });
    expect(input).toHaveValue("1,234.50");
    await user.clear(input);
    await user.type(input, "$2 000.5");
    await user.tab();
    expect(onChange).toHaveBeenLastCalledWith("2000.50");
    expect(input).toHaveValue("2,000.50");
  });

  it("French: comma decimal, space groups", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness locale="fr-CA" onChange={onChange} />);
    const input = screen.getByRole("textbox", { name: "Amount" });
    expect(input).toHaveValue("1 234,50");
    await user.clear(input);
    await user.type(input, "99,9{Enter}");
    expect(onChange).toHaveBeenLastCalledWith("99.90");
  });

  it("unreadable amounts are flagged, not guessed", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByRole("textbox", { name: "Amount" });
    await user.clear(input);
    await user.type(input, "12.345");
    await user.tab();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Enter an amount like 1,234.56.");
    await expectNoAxeViolations();
  });
});

describe("AccountPicker (A-10-T09)", () => {
  function Harness({ types, side }: { types?: AccountType[]; side?: "debit" | "credit" }) {
    const [value, setValue] = useState<string | null>(null);
    return (
      <>
        <label htmlFor="acc">Account</label>
        <AccountPicker
          id="acc"
          accounts={sampleAccounts}
          value={value}
          onChange={setValue}
          types={types}
          side={side}
          typeLabels={typeLabels}
          emptyMessage="No accounts match."
        />
        <output>{value ?? "none"}</output>
      </>
    );
  }

  it("searches by code or name and is keyboard-operable", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByRole("combobox", { name: "Account" });
    await user.type(input, "cheq");
    expect(screen.getAllByRole("option")).toHaveLength(1);
    await user.keyboard("{Enter}");
    expect(screen.getByRole("status")).toHaveTextContent("a1000");
    await user.clear(input);
    await user.type(input, "2100{Enter}");
    expect(screen.getByRole("status")).toHaveTextContent("a2100");
  });

  it("sales context: revenue only, grouped; archived never offered", async () => {
    const user = userEvent.setup();
    render(<Harness types={["revenue"]} />);
    await user.click(screen.getByRole("combobox", { name: "Account" }));
    const labels = screen.getAllByRole("option").map((o) => o.textContent);
    expect(labels).toEqual(["4000 · Sales", "4100 · Consulting revenue"]);
    expect(screen.getByText("Revenue")).toBeInTheDocument();
  });

  it("filters by normal side", async () => {
    const user = userEvent.setup();
    render(<Harness side="debit" />);
    await user.click(screen.getByRole("combobox", { name: "Account" }));
    const labels = screen.getAllByRole("option").map((o) => o.textContent ?? "");
    expect(labels.every((l) => /^[156]/.test(l))).toBe(true);
    expect(labels.some((l) => l.includes("Old telephone"))).toBe(false);
    await expectNoAxeViolations();
  });
});

describe("ContactPicker (A-10-T09)", () => {
  it("limits to a role, hides archived, searches email, offers create", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    const onChange = vi.fn();
    render(
      <>
        <label htmlFor="sup">Supplier</label>
        <ContactPicker
          id="sup"
          contacts={sampleContacts}
          value={null}
          onChange={onChange}
          role="supplier"
          onCreate={onCreate}
          createLabel={(name) => `Create contact "${name}"`}
          emptyMessage="No suppliers match."
        />
      </>,
    );
    const input = screen.getByRole("combobox", { name: "Supplier" });
    await user.click(input);
    expect(screen.getAllByRole("option").map((o) => o.firstChild?.textContent)).toEqual([
      "Northern Lights Bakery Inc.",
      "Hydro Ottawa",
    ]);
    await user.type(input, "billing@");
    expect(screen.getAllByRole("option")).toHaveLength(1);
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith("c3", expect.objectContaining({ name: "Hydro Ottawa" }));

    await user.clear(input);
    await user.type(input, "Rogers");
    expect(screen.getByRole("status")).toHaveTextContent("No suppliers match.");
    await user.click(screen.getByRole("button", { name: 'Create contact "Rogers"' }));
    expect(onCreate).toHaveBeenCalledWith("Rogers");
    await expectNoAxeViolations();
  });

  it("server search: every keystroke calls onSearch and results aren't filtered again", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(
      <ContactPicker
        aria-label="Customer"
        contacts={sampleContacts.slice(0, 1)}
        value={null}
        onChange={vi.fn()}
        onSearch={onSearch}
        emptyMessage="No customers match."
      />,
    );
    await user.type(screen.getByRole("combobox", { name: "Customer" }), "mapel");
    expect(onSearch).toHaveBeenLastCalledWith("mapel");
    expect(screen.getAllByRole("option")).toHaveLength(1);
  });
});
