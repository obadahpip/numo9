import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { CheckboxField, SelectField, TextField } from "./Field";
import { Form, flattenErrors } from "./Form";
import {
  formLabels,
  generalDefaults,
  generalSettingsSchema,
  provinceOptions,
  type GeneralSettings,
} from "./fixtures";

function Settings({
  onSubmit = vi.fn(),
  defaults = generalDefaults,
  onLeave,
}: {
  onSubmit?: (values: GeneralSettings) => void | Promise<void>;
  defaults?: GeneralSettings;
  onLeave?: (href: string) => void;
}) {
  return (
    <>
      <a href="/o/maple/contacts">Contacts</a>
      <Form
        aria-label="General settings"
        schema={generalSettingsSchema}
        defaultValues={defaults}
        onSubmit={onSubmit}
        labels={formLabels}
        onLeave={onLeave}
      >
        <TextField name="legalName" label="Legal name" required hint="As registered with the CRA" />
        <SelectField name="province" label="Province" options={provinceOptions} required />
        <TextField name="postalCode" label="Postal code" required />
        <CheckboxField name="newsletter" label="Send me product news" />
        <button type="submit">Submit</button>
      </Form>
    </>
  );
}

const blank: GeneralSettings = { legalName: "", province: "", postalCode: "", newsletter: false };

describe("Form kit (A-10-T07)", () => {
  it("on a failed submit, focus moves to the first field with an error", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Settings defaults={blank} onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(screen.getByRole("textbox", { name: /Legal name/ })).toHaveFocus());
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows inline errors wired to the field and a summary with links in on-screen order", async () => {
    const user = userEvent.setup();
    render(<Settings defaults={{ ...blank, legalName: "12345", postalCode: "M5V2T" }} />);
    await user.click(screen.getByRole("button", { name: "Submit" }));

    const summary = await screen.findByRole("alert");
    expect(within(summary).getByRole("heading")).toHaveTextContent(
      "There are 3 problems with this form",
    );
    const links = within(summary).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual([
      "Legal name: Legal name can't be only numbers — it prints on every statement. Enter the registered business name, e.g. 'Refined Interiors Inc.'",
      "Province: Choose the Province where the business is registered.",
      "Postal code: Postal code should look like 'M5V 2T6'.",
    ]);

    const postal = screen.getByRole("textbox", { name: /Postal code/ });
    expect(postal).toHaveAttribute("aria-invalid", "true");
    expect(postal).toHaveAccessibleDescription("Postal code should look like 'M5V 2T6'.");

    await user.click(links[2]!);
    expect(postal).toHaveFocus();
  });

  it("the summary shrinks as errors are fixed and goes away when none remain", async () => {
    const user = userEvent.setup();
    render(<Settings defaults={{ ...generalDefaults, postalCode: "bad", legalName: "" }} />);
    await user.click(screen.getByRole("button", { name: "Submit" }));
    const summary = await screen.findByRole("alert");
    expect(within(summary).getAllByRole("link")).toHaveLength(2);

    await user.type(screen.getByRole("textbox", { name: /Legal name/ }), "Maple Leaf Supply Ltd.");
    await user.tab();
    await waitFor(() =>
      expect(within(screen.getByRole("alert")).getAllByRole("link")).toHaveLength(1),
    );

    const postal = screen.getByRole("textbox", { name: /Postal code/ });
    await user.clear(postal);
    await user.type(postal, "M5V 2T6");
    await user.tab();
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("submits parsed values when valid", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Settings onSubmit={onSubmit} />);
    const name = screen.getByRole("textbox", { name: /Legal name/ });
    await user.clear(name);
    await user.type(name, "  Northern Lights Bakery Inc. ");
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        { ...generalDefaults, legalName: "Northern Lights Bakery Inc." },
        expect.anything(),
      ),
    );
  });

  it("shows the sticky save bar only with unsaved changes; Discard resets; Ctrl+S saves", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Settings onSubmit={onSubmit} />);
    expect(screen.queryByRole("button", { name: "Save settings" })).toBeNull();

    const postal = screen.getByRole("textbox", { name: /Postal code/ });
    await user.clear(postal);
    await user.type(postal, "H2X 1Y4");
    expect(screen.getByText("You have unsaved changes.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(postal).toHaveValue("M5V 2T6");
    expect(screen.queryByText("You have unsaved changes.")).toBeNull();

    await user.clear(postal);
    await user.type(postal, "H2X 1Y4");
    await user.keyboard("{Control>}s{/Control}");
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ postalCode: "H2X 1Y4" }),
        expect.anything(),
      ),
    );
  });

  it("unsaved-changes guard: link click asks first; Stay keeps; Leave navigates", async () => {
    const user = userEvent.setup();
    const onLeave = vi.fn();
    render(<Settings onLeave={onLeave} />);
    await user.type(screen.getByRole("textbox", { name: /Postal code/ }), "x");

    await user.click(screen.getByRole("link", { name: "Contacts" }));
    const dialog = await screen.findByRole("dialog", { name: "Leave without saving?" });
    await user.click(within(dialog).getByRole("button", { name: "Stay on this page" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(onLeave).not.toHaveBeenCalled();

    await user.click(screen.getByRole("link", { name: "Contacts" }));
    await user.click(await screen.findByRole("button", { name: "Leave without saving" }));
    expect(onLeave).toHaveBeenCalledWith("/o/maple/contacts");
  });

  it("unsaved-changes guard: beforeunload is blocked only while dirty", async () => {
    const user = userEvent.setup();
    render(<Settings />);
    const clean = new Event("beforeunload", { cancelable: true });
    act(() => {
      window.dispatchEvent(clean);
    });
    expect(clean.defaultPrevented).toBe(false);

    await user.type(screen.getByRole("textbox", { name: /Postal code/ }), "x");
    const dirty = new Event("beforeunload", { cancelable: true });
    fireEvent(window, dirty);
    expect(dirty.defaultPrevented).toBe(true);
  });

  it("has no axe violations with errors shown", async () => {
    const user = userEvent.setup();
    render(<Settings defaults={blank} />);
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await screen.findByRole("alert");
    await expectNoAxeViolations();
  });
});

describe("flattenErrors", () => {
  it("flattens nested errors to dotted names", () => {
    expect(
      flattenErrors({
        name: { type: "too_small", message: "Enter a name" },
        address: { postalCode: { type: "invalid", message: "Bad postal code" } },
      }),
    ).toEqual([
      { name: "name", message: "Enter a name" },
      { name: "address.postalCode", message: "Bad postal code" },
    ]);
  });
});
