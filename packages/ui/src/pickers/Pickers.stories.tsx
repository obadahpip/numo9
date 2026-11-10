import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";

import type { IsoDate } from "../format/dates";
import { AccountPicker } from "./AccountPicker";
import { ContactPicker } from "./ContactPicker";
import { CurrencyInput } from "./CurrencyInput";
import { DatePicker } from "./DatePicker";
import { dateLabels, sampleAccounts, sampleContacts, typeLabels } from "./fixtures";
import { isValidPostalCode } from "./postalCode";
import { PostalCodeInput } from "./PostalCodeInput";
import { ProvincePicker } from "./ProvincePicker";

/**
 * Pickers (A-10-T09). All keyboard-operable: the date field reads `26/10`, `oct 26`, `+30`,
 * `today`; Alt+↓ opens the calendar. Amounts read `1,234.5` or `$1 234,50`.
 */
const meta: Meta = { title: "Forms/Pickers" };
export default meta;
type Story = StoryObj;

function Row({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}

function AllPickers({ locale }: { locale: "en-CA" | "fr-CA" }) {
  const [invoiceDate, setInvoiceDate] = useState<IsoDate | null>("2026-10-15");
  const [due, setDue] = useState<IsoDate | null>(null);
  const [postal, setPostal] = useState("m5v2t6");
  const [amount, setAmount] = useState<string | null>("1234.5");
  const [account, setAccount] = useState<string | null>(null);
  const [contact, setContact] = useState<string | null>(null);
  return (
    <div className="grid max-w-md gap-5">
      <Row label="Invoice date" htmlFor="inv-date">
        <DatePicker
          id="inv-date"
          value={invoiceDate}
          onChange={setInvoiceDate}
          locale={locale}
          today="2026-10-15"
          labels={dateLabels}
        />
      </Row>
      <Row label="Due date (shortcuts from the invoice date)" htmlFor="due-date">
        <DatePicker
          id="due-date"
          value={due}
          onChange={setDue}
          base={invoiceDate}
          locale={locale}
          today="2026-10-15"
          labels={dateLabels}
        />
      </Row>
      <Row label="Province">
        <ProvincePicker
          aria-label="Province"
          locale={locale}
          defaultValue="ON"
          groupLabels={{ provinces: "Provinces", territories: "Territories" }}
        />
      </Row>
      <Row label="Postal code" htmlFor="postal">
        <PostalCodeInput
          id="postal"
          value={postal}
          onChange={setPostal}
          invalid={postal.length === 7 && !isValidPostalCode(postal)}
        />
      </Row>
      <Row label="Amount" htmlFor="amount">
        <CurrencyInput
          id="amount"
          locale={locale}
          value={amount}
          onChange={setAmount}
          unreadableMessage="Enter an amount like 1,234.56."
        />
      </Row>
      <Row label="Account (sales line: revenue only)" htmlFor="account">
        <AccountPicker
          id="account"
          accounts={sampleAccounts}
          types={["revenue"]}
          value={account}
          onChange={setAccount}
          typeLabels={typeLabels}
          emptyMessage="No accounts match."
        />
      </Row>
      <Row label="Supplier" htmlFor="supplier">
        <ContactPicker
          id="supplier"
          contacts={sampleContacts}
          role="supplier"
          value={contact}
          onChange={setContact}
          emptyMessage="No suppliers match."
          onCreate={() => undefined}
          createLabel={(name) => `Create contact "${name}"`}
        />
      </Row>
    </div>
  );
}

export const English: Story = { render: () => <AllPickers locale="en-CA" /> };
export const French: Story = { render: () => <AllPickers locale="fr-CA" /> };
