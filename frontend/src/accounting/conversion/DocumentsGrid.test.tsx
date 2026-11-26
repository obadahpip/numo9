import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { DocumentInput } from "./api";
import { DocumentsGrid, emptyRow, pasteInto } from "./DocumentsGrid";

/**
 * C-05-T12 — open invoices / bills grids, paste-friendly: 20 rows pasted from a spreadsheet
 * become 20 rows, checked on the server (dry run) and added all at once; a row the server refuses
 * is flagged on its cell and listed, and nothing is added.
 */
const TSV = [
  "Customer\tNumber\tDate\tDue date\tTotal\tStill owed",
  ...Array.from(
    { length: 20 },
    (_, i) => `ON Customer Ltd\tINV-${900 + i}\t15/11/2025\t2025-12-15\t$1,${i}00.00\t`,
  ),
].join("\n");

let sent: { dry_run: boolean; rows: DocumentInput[] }[] = [];
let refuse = false;
beforeEach(() => {
  sent = [];
  refuse = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((_url, init) => {
        const body = JSON.parse(String(init?.body ?? "{}"));
        sent.push(body);
        const rows = body.rows.map((_: unknown, i: number) => ({
          row: i + 1,
          ok: !(refuse && i === 4),
          errors:
            refuse && i === 4
              ? [
                  {
                    field: "number",
                    code: "conversion.document.number_taken",
                    message: "There's already an invoice INV-904.",
                  },
                ]
              : [],
          id: null,
        }));
        const errors = rows.filter((r: { ok: boolean }) => !r.ok).length;
        return {
          status: errors ? 400 : body.dry_run ? 200 : 201,
          body: {
            dry_run: body.dry_run,
            rows,
            ok: rows.length - errors,
            errors,
            written: errors || body.dry_run ? 0 : rows.length,
          },
        };
      }),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

it("pasteInto skips a header, fills from the cell on and adds rows", () => {
  const cells = TSV.split("\n").map((r) => r.split("\t"));
  const { rows, count } = pasteInto([emptyRow()], cells, 0, "contact", "en-CA");
  expect(count).toBe(20);
  expect(rows).toHaveLength(20);
  expect(rows[3]).toMatchObject({
    contact: "ON Customer Ltd",
    number: "INV-903",
    total: "$1,300.00",
  });
  const later = pasteInto(rows, [["99.00", "10.00"]], 2, "total", "en-CA").rows;
  expect(later[2]).toMatchObject({ number: "INV-902", total: "99.00", outstanding: "10.00" });
});

it("paste 20 rows → 20 documents validated, then added", async () => {
  const user = userEvent.setup();
  const changed = vi.fn();
  renderWithIntl(
    <DocumentsGrid
      org="acme"
      kind="invoice"
      documents={[]}
      readOnly={false}
      onChanged={changed}
      today="2026-01-10"
    />,
  );
  fireEvent.paste(screen.getByLabelText("Customer, row 1"), {
    clipboardData: { getData: () => TSV },
  });
  expect(await screen.findByText("20 rows pasted.")).toBeInTheDocument();
  expect(document.querySelectorAll("[data-row]")).toHaveLength(20);
  await user.click(screen.getByRole("button", { name: "Verify the rows" }));
  expect(await screen.findByText("All 20 rows are ready to add.")).toBeInTheDocument();
  const check = sent[0]!;
  expect(check.dry_run).toBe(true);
  expect(check.rows).toHaveLength(20);
  expect(check.rows[3]).toEqual({
    contact: "ON Customer Ltd",
    number: "INV-903",
    date: "2025-11-15",
    due_date: "2025-12-15",
    total: "1300.00",
    reference: "",
  });
  await user.click(screen.getByRole("button", { name: "Add 20 documents" }));
  expect(await screen.findByText("20 documents added.")).toBeInTheDocument();
  expect(sent[1]!.dry_run).toBe(false);
  expect(changed).toHaveBeenCalled();
});

it("a refused row is flagged and nothing is added", async () => {
  const user = userEvent.setup();
  refuse = true;
  renderWithIntl(
    <DocumentsGrid
      org="acme"
      kind="invoice"
      documents={[]}
      readOnly={false}
      onChanged={() => undefined}
      today="2026-01-10"
    />,
  );
  fireEvent.paste(screen.getByLabelText("Customer, row 1"), {
    clipboardData: { getData: () => TSV },
  });
  await user.click(await screen.findByRole("button", { name: "Add 20 documents" }));
  expect(await screen.findByText(/1 row has a problem: nothing was added/)).toBeInTheDocument();
  expect(screen.getByText("Row 5: There's already an invoice INV-904.")).toBeInTheDocument();
  expect(screen.getByLabelText("Invoice no., row 5")).toHaveAttribute("aria-invalid", "true");
  expect(document.querySelectorAll("[data-row]")).toHaveLength(20);
});

it("bills: supplier columns, saved list with what is owed", () => {
  renderWithIntl(
    <DocumentsGrid
      org="acme"
      kind="bill"
      readOnly
      onChanged={() => undefined}
      documents={[
        {
          id: "d1",
          kind: "bill",
          document_id: "b1",
          number: "OB-0001",
          supplier_invoice_no: "C-7781",
          contact: { id: "c1", name: "Cedar Supply Co." },
          date: "2025-12-10",
          due_date: null,
          reference: "",
          total: "565.00",
          outstanding: "300.00",
          amount_due: "300.00",
          status: "partially_paid",
        },
      ]}
    />,
  );
  expect(screen.getByRole("columnheader", { name: "Supplier's invoice no." })).toBeInTheDocument();
  expect(screen.getByText("C-7781")).toBeInTheDocument();
  expect(screen.getByText("1 document · still owed $300.00")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Remove C-7781" })).not.toBeInTheDocument();
});
