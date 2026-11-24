import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { parseRecipients, type InvoiceEmailDefaults } from "./api";
import { InvoiceEmailComposer } from "./InvoiceEmailComposer";

/**
 * D-03a-T15 — email composer with PDF preview: the defaults fill the form, the PDF preview shows
 * the invoice PDF, bad addresses are caught before sending, Send posts what was typed and the
 * send appears in the history with its viewed status; a draft can't be sent.
 */
const defaults = (over: Partial<InvoiceEmailDefaults> = {}): InvoiceEmailDefaults => ({
  to: ["ap@cedar.ca"],
  subject: "Invoice INV-0001 from Maple Leaf Supply Ltd.",
  message: "Hello,\n\nHere is invoice INV-0001.",
  language: "en-ca",
  file_name: "invoice-INV-0001.pdf",
  sendable: true,
  sent_at: null,
  viewed_at: null,
  sends: [],
  ...over,
});

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => "blob:pdf");
  URL.revokeObjectURL = vi.fn();
});

let state: InvoiceEmailDefaults;
let posted: unknown[] = [];

function serve(initial: InvoiceEmailDefaults) {
  state = initial;
  posted = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (init?.method === "POST") {
          const body = JSON.parse(String(init.body)) as { to: string[]; subject: string };
          posted.push(body);
          const row = {
            id: "s1",
            recipients: body.to,
            subject: body.subject,
            language: "en-ca",
            file_name: state.file_name,
            sent_at: "2026-06-16T14:00:00Z",
            sent_by: "Sam Patel",
            viewed_at: null,
          };
          state = { ...state, sends: [row] };
          return { status: 201, body: row };
        }
        if (url.endsWith("/email")) return { body: state };
        if (url.endsWith("/pdf")) return { body: "%PDF" };
        return { status: 404, body: {} };
      }),
    ),
  );
}

const render = () => renderWithIntl(<InvoiceEmailComposer org="acme" id="inv-1" />);

describe("InvoiceEmailComposer", () => {
  it("fills the form from the defaults and previews the PDF", async () => {
    serve(defaults());
    render();
    expect(await screen.findByLabelText("To")).toHaveValue("ap@cedar.ca");
    expect(screen.getByLabelText("Subject")).toHaveValue(
      "Invoice INV-0001 from Maple Leaf Supply Ltd.",
    );
    expect(screen.getByText("Attached: invoice-INV-0001.pdf")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Preview PDF" }));
    expect(await screen.findByTitle("Invoice PDF preview")).toHaveAttribute("src", "blob:pdf");
    expect(screen.getByRole("button", { name: "Hide preview" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("refuses bad addresses before sending", async () => {
    serve(defaults());
    render();
    const to = await screen.findByLabelText("To");
    await userEvent.clear(to);
    await userEvent.type(to, "ap@cedar.ca, not-an-email");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getByText("Review these addresses: not-an-email")).toBeInTheDocument();
    expect(to).toHaveAttribute("aria-invalid", "true");
    expect(posted).toEqual([]);
  });

  it("sends and lists the send with its viewed status", async () => {
    serve(defaults());
    render();
    const to = await screen.findByLabelText("To");
    await userEvent.type(to, ", boss@cedar.ca");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Invoice sent to ap@cedar.ca, boss@cedar.ca.",
      ),
    );
    expect(posted).toEqual([
      {
        to: ["ap@cedar.ca", "boss@cedar.ca"],
        subject: "Invoice INV-0001 from Maple Leaf Supply Ltd.",
        message: "Hello,\n\nHere is invoice INV-0001.",
      },
    ]);
    expect(await screen.findByText("Not viewed yet")).toBeInTheDocument();
  });

  it("explains that a draft can't be sent", async () => {
    serve(defaults({ sendable: false }));
    render();
    expect(await screen.findByRole("note")).toHaveTextContent(
      "Approve the invoice before you email it.",
    );
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});

describe("parseRecipients", () => {
  it("splits, de-duplicates and checks addresses", () => {
    expect(parseRecipients("a@x.ca; b@x.ca a@x.ca, nope")).toEqual({
      valid: ["a@x.ca", "b@x.ca"],
      invalid: ["nope"],
    });
  });
});
