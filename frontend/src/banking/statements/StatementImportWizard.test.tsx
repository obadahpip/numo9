import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { bankAccount, ORG, serveJson } from "../fixtures";
import {
  gridRows,
  layoutComplete,
  padColumns,
  type Layout,
  type Preview,
  type Upload,
} from "./api";
import { StatementImportWizard } from "./StatementImportWizard";

/**
 * F-02-T12 — wizard: Upload → Map → Preview → Confirm. The detection message names the format,
 * encoding and delimiter; the mapping grid shows the first 5 rows with a dropdown per column and
 * sends the edited layout; the preview tabs carry the counts; "Skip errors" unlocks Import.
 */
afterEach(() => vi.unstubAllGlobals());

const ID = "6ca1b880-64f7-4053-80e3-0c3618895553";
const LAYOUT: Layout = {
  columns: ["date", "description", "amount"],
  date_format: "YYYY-MM-DD",
  sign: "signed",
  has_header: true,
  skip_rows: 0,
  decimal_separator: ".",
};
const importRow = {
  id: "imp1",
  bank_account: ID,
  file_name: "june.csv",
  file_format: "csv",
  source: "file",
  status: "pending" as const,
  status_label: "Pending",
  mapping: null,
  counts: { total: 7, new: 0, duplicate: 0, error: 0 },
  created_at: "2026-07-01T12:00:00Z",
  created_by: null,
  committed_at: null,
  undone_at: null,
};
const UPLOAD: Upload = {
  import: importRow,
  format: "csv",
  encoding: "cp1252",
  delimiter: ";",
  warnings: [],
  tabular: true,
  lines: 7,
  sample: {
    width: 3,
    rows: [
      { row: 1, cells: ["Date", "Libellé", "Montant"] },
      ...Array.from({ length: 7 }, (_, i) => ({
        row: i + 2,
        cells: [`2026-06-0${i + 1}`, `Café ${i + 1}`, `-${i + 1}.00`],
      })),
    ],
  },
  layout: LAYOUT,
  mapping: {
    id: "m-generic",
    name: "Generic (date, description, amount)",
    institution: "",
    builtin: true,
    layout: LAYOUT,
    score: 0.9,
  },
  mappings: [
    {
      id: "m-generic",
      name: "Generic (date, description, amount)",
      institution: "",
      builtin: true,
      layout: LAYOUT,
    },
  ],
  date_formats: ["YYYY-MM-DD"],
  date_ambiguous: false,
  choices: {
    roles: ["date", "description", "amount", "ignore"],
    signs: ["signed", "inverted", "debit_credit"],
    date_formats: ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"],
  },
};
const line = (row: number, status: "new" | "duplicate" | "error") => ({
  row,
  date: status === "error" ? null : "2026-06-01",
  amount: status === "error" ? null : "-1.00",
  description: `Café ${row}`,
  payee: "",
  reference: "",
  fitid: "",
  status,
  reasons:
    status === "error"
      ? [{ code: "banking.statement.row.date_format", message: "Row 8: date 'x' doesn't match" }]
      : [],
});
const PREVIEW: Preview = {
  import: importRow,
  counts: { total: 7, new: 5, duplicate: 1, error: 1 },
  balances: { opening: null, closing: null },
  warnings: [],
  layout: LAYOUT,
  count: 7,
  results: [...[2, 3, 4, 5, 6].map((r) => line(r, "new")), line(7, "duplicate"), line(8, "error")],
};

function serve(calls: { url: string; body: unknown }[], upload: Upload = UPLOAD) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        const body = typeof init?.body === "string" ? JSON.parse(init.body) : init?.body;
        calls.push({ url, body });
        if (url.endsWith(`/bank-accounts/${ID}`)) return { body: bankAccount({ id: ID }) };
        if (url.endsWith("/imports")) return { status: 201, body: upload };
        if (url.endsWith("/preview")) return { body: PREVIEW };
        if (url.endsWith("/commit"))
          return {
            body: {
              import: { ...importRow, status: "committed", counts: PREVIEW.counts },
            },
          };
        return { status: 404, body: {} };
      }),
    ),
  );
}

it("imports a CSV through the four steps", async () => {
  const calls: { url: string; body: unknown }[] = [];
  serve(calls);
  const user = userEvent.setup();
  renderWithIntl(<StatementImportWizard org={ORG} account={ID} />);
  expect(screen.getByRole("heading", { name: "Import a statement" })).toBeVisible();
  expect(screen.getByText("Drop your statement file here")).toBeVisible();
  await user.upload(
    screen.getByLabelText("Choose a file"),
    new File(["Date;Libellé;Montant\n"], "june.csv", { type: "text/csv" }),
  );
  expect(
    await screen.findByText("Read as CSV (Windows-1252, semicolon-separated) — 7 lines."),
  ).toBeVisible();
  expect(
    screen.getByText("Mapping: Generic (date, description, amount) (recognised automatically)."),
  ).toBeVisible();
  const grid = screen.getByRole("table", { name: "First rows of the file" });
  expect(within(grid).getAllByRole("row")).toHaveLength(6); // dropdowns + the first 5 rows
  expect(within(grid).getByText("Libellé")).toBeVisible();
  await user.selectOptions(within(grid).getByLabelText("Column 2"), "payee");
  expect(screen.getByLabelText("Saved mapping")).toHaveValue("");

  await user.click(screen.getByRole("button", { name: "Preview" }));
  const tabs = await screen.findByRole("tablist", { name: "Lines by status" });
  expect(within(tabs).getByRole("tab", { name: /New/ })).toHaveTextContent("5");
  expect(within(tabs).getByRole("tab", { name: /Duplicates/ })).toHaveTextContent("1");
  expect(within(tabs).getByRole("tab", { name: /Errors/ })).toHaveTextContent("1");
  const sent = calls.find((c) => c.url.endsWith("/preview"))?.body as {
    layout: Layout;
    mapping: string;
  };
  expect(sent.layout.columns).toEqual(["date", "payee", "amount"]);
  expect(sent.mapping).toBe("m-generic");

  await user.click(screen.getByRole("tab", { name: /Errors/ }));
  expect(await screen.findByText("Row 8: date 'x' doesn't match")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Continue" }));
  expect(screen.getByText("5 new lines will be imported into TD Business Chequing.")).toBeVisible();
  const importButton = screen.getByRole("button", { name: "Import 5 lines" });
  expect(importButton).toBeDisabled(); // errors and "skip errors" is off
  await user.click(screen.getByRole("button", { name: "Back" }));
  await user.click(screen.getByRole("switch", { name: "Skip errors and import valid lines" }));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("button", { name: "Import 5 lines" }));
  expect(await screen.findByRole("link", { name: "Go to the account" })).toHaveAttribute(
    "href",
    `/o/${ORG}/banking/${ID}`,
  );
  const commit = calls.find((c) => c.url.endsWith("/commit"))?.body as { skip_errors: boolean };
  expect(commit.skip_errors).toBe(true);
});

it("an OFX file skips the Map step", async () => {
  const calls: { url: string; body: unknown }[] = [];
  serve(calls, {
    import: { ...importRow, file_format: "qfx" },
    format: "qfx",
    encoding: "utf-8",
    delimiter: "",
    warnings: [],
    tabular: false,
    lines: 3,
  });
  const user = userEvent.setup();
  renderWithIntl(<StatementImportWizard org={ORG} account={ID} />);
  await user.upload(screen.getByLabelText("Choose a file"), new File(["<OFX>"], "june.qfx"));
  expect(await screen.findByText("Read as QFX — 3 lines. No column mapping needed.")).toBeVisible();
  expect(await screen.findByRole("tablist", { name: "Lines by status" })).toBeVisible();
  const sent = calls.find((c) => c.url.endsWith("/preview"))?.body as { layout: unknown };
  expect(sent.layout).toBeNull();
});

it("shows the server's reason when the file is refused", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) =>
        url.endsWith("/imports")
          ? {
              status: 415,
              body: {
                code: "banking.statement.file.type",
                detail: "scan.pdf isn't a statement file Numo9 can read.",
              },
            }
          : { body: bankAccount({ id: ID }) },
      ),
    ),
  );
  const user = userEvent.setup({ applyAccept: false });
  renderWithIntl(<StatementImportWizard org={ORG} account={ID} />);
  await user.upload(screen.getByLabelText("Choose a file"), new File(["%PDF"], "scan.pdf"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The file couldn't be imported: scan.pdf isn't a statement file Numo9 can read.",
  );
});

it("helpers: grid rows, complete layouts, padded columns", () => {
  const rows = UPLOAD.sample!.rows;
  const withTitle = gridRows(rows, { has_header: true, skip_rows: 1 });
  expect(withTitle.header?.row).toBe(2);
  expect(withTitle.data.map((r) => r.row)).toEqual([3, 4, 5, 6, 7]);
  expect(gridRows(rows, { has_header: false, skip_rows: 0 }).data[0]?.row).toBe(1);
  expect(layoutComplete(LAYOUT)).toBe(true);
  expect(layoutComplete({ ...LAYOUT, sign: "debit_credit" })).toBe(false);
  expect(layoutComplete({ ...LAYOUT, columns: ["description", "amount"] })).toBe(false);
  expect(padColumns(["date"], 3)).toEqual(["date", "ignore", "ignore"]);
});
