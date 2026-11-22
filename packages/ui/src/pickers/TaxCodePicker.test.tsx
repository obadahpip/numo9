import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { sampleTaxCodes, taxTypeLabels } from "./fixtures";
import { TaxCodePicker, taxCodeOffered, type TaxCodeSide } from "./TaxCodePicker";

/**
 * G-01-T14 — shared TaxCodePicker: type badges; sales mode excludes purchase codes; only codes in
 * force on the document date; the account default first; a stale stored value stays visible,
 * flagged.
 */
function Harness({
  side,
  date = "2026-06-15",
  initial = null,
  accountDefault,
  onChange = vi.fn(),
}: {
  side: TaxCodeSide;
  date?: string;
  initial?: string | null;
  accountDefault?: string;
  onChange?: (id: string | null) => void;
}) {
  const [value, setValue] = useState<string | null>(initial);
  return (
    <>
      <label htmlFor="tax">Tax code</label>
      <TaxCodePicker
        id="tax"
        codes={sampleTaxCodes}
        value={value}
        onChange={(id) => {
          setValue(id);
          onChange(id);
        }}
        side={side}
        date={date}
        accountDefault={accountDefault}
        typeLabels={taxTypeLabels}
        defaultLabel="Account default"
        othersLabel="All codes"
        expiredLabel="Not in force on this date"
        emptyMessage="No tax code matches"
      />
    </>
  );
}

async function open() {
  const user = userEvent.setup();
  await user.click(screen.getByLabelText("Tax code"));
  return { user, list: await screen.findByRole("listbox") };
}

it("shows type badges; sales mode excludes purchase codes and ended rates", async () => {
  const { container } = render(<Harness side="sales" />);
  const { list } = await open();
  const names = within(list)
    .getAllByRole("option")
    .map((o) => o.textContent);
  expect(names.some((n) => n?.includes("on purchases"))).toBe(false);
  expect(names.some((n) => n?.includes("RST 8 %"))).toBe(false);
  const on = within(list).getByRole("option", { name: /HST 13 % \(Ontario\) on sales/ });
  expect(within(on).getByText("Taxable")).toBeVisible();
  expect(within(list).getByRole("option", { name: /Zero-rated on sales/ })).toHaveTextContent(
    "Zero-rated",
  );
  expect(within(list).getByRole("option", { name: /Exempt on sales/ })).toHaveTextContent("Exempt");
  await expectNoAxeViolations(container);
});

it("offers purchase codes only in purchase mode and picks one", async () => {
  const onChange = vi.fn();
  render(<Harness side="purchase" onChange={onChange} />);
  const { user, list } = await open();
  expect(within(list).getAllByRole("option")).toHaveLength(1);
  await user.click(within(list).getByRole("option", { name: /on purchases/ }));
  expect(onChange).toHaveBeenCalledWith("p-on");
});

it("lists the account default first and searches by key or rate", async () => {
  render(<Harness side="sales" accountDefault="sales.QC.standard" />);
  const { user, list } = await open();
  const options = within(list).getAllByRole("option");
  expect(options[0]).toHaveTextContent("Quebec");
  expect(screen.getByText("Account default")).toBeVisible();
  await user.type(screen.getByLabelText("Tax code"), "14.975");
  expect(within(await screen.findByRole("listbox")).getAllByRole("option")).toHaveLength(1);
});

it("keeps a stored ended version visible, flagged; date decides what is offered", async () => {
  render(<Harness side="sales" initial="s-mb8" />);
  const { list } = await open();
  expect(within(list).getByRole("option", { name: /RST 8 %/ })).toHaveTextContent(
    "Not in force on this date",
  );
  expect(taxCodeOffered(sampleTaxCodes[2]!, "sales", "2018-03-01")).toBe(true);
  expect(taxCodeOffered(sampleTaxCodes[2]!, "sales", "2019-07-01")).toBe(false);
  expect(taxCodeOffered(sampleTaxCodes[5]!, "sales", "2026-01-01")).toBe(false);
});
