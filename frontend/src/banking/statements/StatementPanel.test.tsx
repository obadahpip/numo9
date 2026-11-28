import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { ORG, serveJson } from "../fixtures";
import type { StatementImport, StatementLine } from "./api";
import { StatementPanel, type StatementLineAction } from "./StatementPanel";

/**
 * F-02-T13 — statement lines and import history on the account page: the "Uncoded" badge equals
 * the API's count of UNCODED lines; the status filters ask the server; each row has an actions
 * menu other features can add to; Undo of an import refreshes the lists.
 */
afterEach(() => vi.unstubAllGlobals());

const ID = "6ca1b880-64f7-4053-80e3-0c3618895553";
const line = (id: string, status: StatementLine["status"], over: Partial<StatementLine> = {}) => ({
  id,
  date: "2026-06-03",
  amount: "-4.25",
  description: `TIM HORTONS ${id}`,
  payee: "",
  reference: "",
  fitid: "",
  status,
  status_label: status[0]!.toUpperCase() + status.slice(1),
  import: { id: "imp1", file_name: "rbc.csv" },
  ...over,
});
const LINES = [
  line("1", "uncoded"),
  line("2", "uncoded"),
  line("3", "coded"),
  line("4", "matched"),
];
const IMPORT: StatementImport = {
  id: "imp1",
  bank_account: ID,
  file_name: "rbc.csv",
  file_format: "csv",
  source: "file",
  status: "committed",
  status_label: "Committed",
  mapping: { id: "m", name: "RBC Royal Bank" },
  counts: { total: 4, new: 4, duplicate: 0, error: 0 },
  created_at: "2026-07-01T12:00:00Z",
  created_by: { name: "Dana Lee" },
  committed_at: "2026-07-01T12:00:00Z",
  undone_at: null,
  in_use: 0,
  can_undo: true,
};

function serve(urls: string[], state: { undone: boolean }) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        if (url.includes("/statement-lines")) {
          const all = state.undone ? [] : LINES;
          const wanted = new URL(url, "http://x").searchParams.get("status");
          const counts = { all: all.length, uncoded: 0, coded: 0, matched: 0, ignored: 0 };
          for (const l of all) counts[l.status] += 1;
          const results = wanted ? all.filter((l) => l.status === wanted) : all;
          return { body: { counts, count: results.length, results } };
        }
        if (url.endsWith("/imports"))
          return {
            body: {
              results: [
                state.undone ? { ...IMPORT, status: "undone", status_label: "Undone" } : IMPORT,
              ],
            },
          };
        if (url.endsWith("/undo")) {
          state.undone = true;
          return { body: { import: { ...IMPORT, status: "undone" } } };
        }
        return { status: 404, body: {} };
      }),
    ),
  );
}

it("the Uncoded badge equals the count of uncoded lines; filters ask the server", async () => {
  const urls: string[] = [];
  serve(urls, { undone: false });
  const user = userEvent.setup();
  renderWithIntl(<StatementPanel org={ORG} account={ID} currency="CAD" />);
  expect(await screen.findByText("Uncoded: 2")).toBeVisible();
  const table = await screen.findByRole("table", { name: "Statement lines" });
  expect(within(table).getAllByRole("row")).toHaveLength(5);
  await user.click(screen.getByRole("button", { name: "Uncoded (2)" }));
  expect(await within(table).findAllByRole("row")).toHaveLength(3);
  expect(urls.some((u) => u.endsWith("/statement-lines?status=uncoded"))).toBe(true);
  expect(screen.getByRole("button", { name: "Uncoded (2)" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

it("each row has an actions menu that features can add to", async () => {
  const urls: string[] = [];
  serve(urls, { undone: false });
  const run = vi.fn();
  const extra: StatementLineAction = { id: "rule", label: () => "Create rule from line", run };
  const user = userEvent.setup();
  renderWithIntl(
    <StatementPanel
      org={ORG}
      account={ID}
      currency="CAD"
      actions={[
        {
          id: "show-import",
          label: () => "Show the lines of this import",
          run: (l, p) => p.showImport(l.import!.id, l.import!.file_name),
        },
        extra,
      ]}
    />,
  );
  await user.click(await screen.findByRole("button", { name: /Actions for .* TIM HORTONS 1/ }));
  await user.click(screen.getByRole("button", { name: "Create rule from line" }));
  expect(run).toHaveBeenCalledWith(expect.objectContaining({ id: "1" }), expect.anything());
  await user.click(screen.getByRole("button", { name: /Actions for .* TIM HORTONS 2/ }));
  await user.click(screen.getByRole("button", { name: "Show the lines of this import" }));
  expect(await screen.findByText("Showing the lines of rbc.csv.")).toBeVisible();
  expect(urls.some((u) => u.includes("import=imp1"))).toBe(true);
});

it("undo an import from the history", async () => {
  const urls: string[] = [];
  serve(urls, { undone: false });
  const user = userEvent.setup();
  renderWithIntl(<StatementPanel org={ORG} account={ID} currency="CAD" />);
  const history = await screen.findByRole("table", { name: "Import history" });
  expect(within(history).getByText("RBC Royal Bank", { exact: false })).toBeVisible();
  await user.click(within(history).getByRole("button", { name: "Undo the import of rbc.csv" }));
  expect(await screen.findByText("rbc.csv undone: its lines were removed.")).toBeVisible();
  expect(await screen.findByText("No statement lines yet")).toBeVisible();
  expect(await screen.findByText("Uncoded: 0")).toBeVisible();
});
