"use client";

import { forwardRef, useMemo, useState } from "react";

import { Combobox, type ComboboxOption, type ComboboxProps } from "../primitives/Combobox";

export type ContactRole = "customer" | "supplier";

export interface PickerContact {
  id: string;
  name: string;
  email?: string;
  roles: readonly ContactRole[];
  archived?: boolean;
}

export interface ContactPickerProps extends Omit<
  ComboboxProps,
  "options" | "value" | "onChange" | "footer" | "filter"
> {
  contacts: readonly PickerContact[];
  value: string | null;
  onChange: (contactId: string | null, contact: PickerContact | null) => void;
  /** Only customers (invoices, quotes) or suppliers (bills, POs). */
  role?: ContactRole;
  /** Server search: called as the user types; pass the results back in `contacts`. */
  onSearch?: (query: string) => void;
  /** "Create contact" from the typed name; omit to hide the action. */
  onCreate?: (name: string) => void;
  /** Label of the create action for the typed name, e.g. (n) → `Create contact "n"`. */
  createLabel?: (name: string) => string;
}

/**
 * Contact picker (A-10-T09): search by name or email, limited to a role; archived contacts are
 * not offered; optional "Create contact" from the typed text (the caller opens the quick-create
 * form). With `onSearch` the list comes from the server and isn't filtered again here.
 */
export const ContactPicker = forwardRef<HTMLInputElement, ContactPickerProps>(
  function ContactPicker(
    { contacts, value, onChange, role, onSearch, onCreate, createLabel, ...props },
    ref,
  ) {
    const [query, setQuery] = useState("");
    const allowed = useMemo(
      () =>
        contacts.filter(
          (contact) =>
            (!contact.archived || contact.id === value) && (!role || contact.roles.includes(role)),
        ),
      [contacts, role, value],
    );
    const options = useMemo<ComboboxOption[]>(
      () =>
        allowed.map((contact) => ({
          value: contact.id,
          label: contact.name,
          description: contact.email,
        })),
      [allowed],
    );
    const typed = query.trim();
    return (
      <Combobox
        ref={ref}
        {...props}
        options={options}
        value={value}
        filter={onSearch ? () => true : undefined}
        onQueryChange={(next) => {
          setQuery(next);
          onSearch?.(next);
        }}
        onChange={(id) => onChange(id, allowed.find((contact) => contact.id === id) ?? null)}
        footer={
          onCreate && createLabel && typed ? (
            <button
              type="button"
              onClick={() => onCreate(typed)}
              className="flex min-h-touch-target w-full items-center rounded-md px-3 text-start text-sm font-semibold text-fg-link hover:bg-surface-muted"
            >
              {createLabel(typed)}
            </button>
          ) : undefined
        }
      />
    );
  },
);
