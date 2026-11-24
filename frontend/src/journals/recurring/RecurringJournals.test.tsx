import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { buildRule, readRule } from "./api";
import { RecurringJournals } from "./RecurringJournals";

/**
 * C-04-T11 — recurring journal editor: the schedule builder makes the rule, the "next 6 dates"
 * are the server's preview of it (the tick's generator), saving sends the template, Pause and
 * Resume toggle it; skipped runs show their reason.
 */
const RENT = "54005400-0000-4000-8000-000000000001";
const BANK = "10001000-0000-4000-8000-000000000002";
const DATES = ["2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30", "2026-10-31", "2026-11-30"];

const account = (id: string, code: string, name: string, type: string, subtype: string) => ({
  id,
  code,
  name,
  type,
  subtype,
  subtype_label: "",
  system_role: "",
  is_bank: false,
  depth: 1,
  has_children: false,
});

const saved = {
  id: "t1",
  name: "Warehouse rent",
  narration: "",
  journal_type: "general",
  lines: [
    {
      account: RENT,
      debit: "2400.00",
      credit: "0.00",
      book: "both",
      contact: null,
      description: "",
    },
    {
      account: BANK,
      debit: "0.00",
      credit: "2400.00",
      book: "both",
      contact: null,
      description: "",
    },
  ],
  rrule: "FREQ=MONTHLY;INTERVAL=1",
  start_date: "2026-01-31",
  end_date: null,
  mode: "post",
  next_run: "2026-06-30",
  paused: false,
  version: 1,
  created_by: "Ava",
  runs: [
    {
      date: "2026-05-31",
      status: "skipped",
      code: "lock.violation",
      message: "The GL lock date is 2026-05-31.",
      journal: null,
    },
  ],
};

let previews: Record<string, unknown>[] = [];
let writes: { method: string; body: Record<string, unknown> }[] = [];

beforeEach(() => {
  previews = [];
  writes = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (url.includes("/accounts?"))
          return {
            body: {
              count: 2,
              results: [
                account(RENT, "5400", "Rent", "expense", "operating_expense"),
                account(BANK, "1000", "Chequing", "asset", "bank"),
              ],
            },
          };
        if (url.endsWith("/journals/recurring/preview")) {
          previews.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
          return { body: { dates: DATES } };
        }
        if (url.endsWith("/journals/recurring") && init?.method === "POST") {
          writes.push({ method: "POST", body: JSON.parse(String(init.body)) });
          return { status: 201, body: saved };
        }
        if (url.endsWith("/journals/recurring/t1") && init?.method === "PATCH") {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          writes.push({ method: "PATCH", body });
          return { body: { ...saved, ...body } };
        }
        if (url.endsWith("/journals/recurring/t1")) return { body: saved };
        if (url.endsWith("/journals/recurring")) return { body: { results: [saved] } };
        return { status: 404, body: {} };
      }),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

async function pick(line: number, typed: string, name: RegExp) {
  const box = screen.getByRole("combobox", { name: `Account, line ${line}` });
  await userEvent.click(box);
  await userEvent.type(box, typed);
  await userEvent.click(await screen.findByRole("option", { name }));
}

it("buildRule / readRule round-trip the builder's choices", () => {
  expect(buildRule("monthly", 1)).toBe("FREQ=MONTHLY;INTERVAL=1");
  expect(buildRule("quarterly", 1)).toBe("FREQ=MONTHLY;INTERVAL=3");
  expect(buildRule("weekly", 2)).toBe("FREQ=WEEKLY;INTERVAL=2");
  expect(buildRule("yearly", 0)).toBe("FREQ=YEARLY;INTERVAL=1");
  for (const [f, n] of [
    ["monthly", 2],
    ["quarterly", 2],
    ["weekly", 3],
    ["yearly", 1],
  ] as const)
    expect(readRule(buildRule(f, n))).toEqual({ frequency: f, every: n });
});

it("new template: the preview is the server's dates; save sends the template", async () => {
  renderWithIntl(<RecurringJournals org="acme" />);
  await userEvent.click(await screen.findByRole("button", { name: "New recurring journal" }));
  await userEvent.type(screen.getByLabelText("Name"), "Warehouse rent");
  await userEvent.selectOptions(screen.getByLabelText("Unit"), "quarterly");
  await waitFor(() =>
    expect(previews.at(-1)).toMatchObject({ rrule: "FREQ=MONTHLY;INTERVAL=3", count: 6 }),
  );
  const preview = screen.getByRole("heading", { name: "Next 6 dates" }).parentElement!;
  await waitFor(() => expect(within(preview).getAllByRole("listitem")).toHaveLength(6));
  expect(preview.querySelector("[data-date='2026-06-30']")).not.toBeNull();

  await pick(1, "5400", /Rent/);
  await userEvent.type(screen.getByLabelText("Debit, line 1"), "2400");
  await pick(2, "1000", /Chequing/);
  await userEvent.type(screen.getByLabelText("Credit, line 2"), "2400");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]?.body).toMatchObject({
    name: "Warehouse rent",
    rrule: "FREQ=MONTHLY;INTERVAL=3",
    lines: [
      { account: RENT, debit: "2400.00", credit: "0.00" },
      { account: BANK, debit: "0.00", credit: "2400.00" },
    ],
  });
});

it("existing template: skipped runs with the reason; Pause and Resume", async () => {
  renderWithIntl(<RecurringJournals org="acme" />);
  await userEvent.click(await screen.findByRole("button", { name: "Warehouse rent" }));
  expect(await screen.findByText(/skipped: The GL lock date is 2026-05-31\./)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Pause" }));
  await waitFor(() => expect(writes.at(-1)).toEqual({ method: "PATCH", body: { paused: true } }));
  expect(await screen.findByRole("button", { name: "Resume" })).toBeVisible();
});
