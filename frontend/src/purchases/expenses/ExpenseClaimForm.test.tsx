import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { CHIP_COUNT, ExpenseClaimForm } from "./ExpenseClaimForm";
import { CLAIM_ID, categoriesFixture, claimFixture } from "./fixtures";

/**
 * E-04-T09 — the claimant's form: category chips most used first (the rest under "More
 * categories"), the default tax code, the camera upload (`capture`), save then submit; the
 * server's refusal is shown as it says it.
 */
let calls: { url: string; method: string; body: unknown }[] = [];

function serve(submitAnswer: { status?: number; body: unknown } = { body: claimFixture() }) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        const method = init?.method ?? "GET";
        const body = init?.body ? JSON.parse(String(init.body)) : null;
        calls.push({ url, method, body });
        if (url.endsWith("/expense-claims/categories")) return { body: categoriesFixture() };
        if (url.endsWith("/expense-claims") && method === "POST")
          return { status: 201, body: claimFixture({ status: "draft", number: "" }) };
        if (url.endsWith("/submit")) return submitAnswer;
        if (url.includes("/mileage-rate")) {
          return {
            body: {
              date: "2026-06-15",
              region: "provinces",
              first_tier_rate: "0.73",
              second_tier_rate: "0.67",
              tier_threshold_km: 5000,
              year_to_date_km: "0",
            },
          };
        }
        return { status: 404, body: {} };
      }),
    ),
  );
}

test("chips show the most used categories first, the rest under More categories", async () => {
  serve();
  renderWithIntl(<ExpenseClaimForm org="acme" navigate={vi.fn()} />);
  const chips = await screen.findAllByRole("button", { pressed: false });
  const names = chips.slice(0, CHIP_COUNT).map((c) => c.textContent);
  expect(names[0]).toBe("Travel");
  expect(names[1]).toBe("Meals and entertainment");
  expect(screen.getByRole("combobox", { name: "More categories" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Travel" }));
  expect(screen.getByRole("button", { name: "Travel" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("Tax on the receipt")).toHaveValue("t-on");
  const camera = screen.getByLabelText("Take a photo or choose a file");
  expect(camera).toHaveAttribute("capture", "environment");
  expect(camera).toHaveAttribute("accept", "image/*,application/pdf");
});

test("submit saves the draft then submits it and opens the claim", async () => {
  serve();
  const navigate = vi.fn();
  renderWithIntl(<ExpenseClaimForm org="acme" navigate={navigate} />);
  await userEvent.type(await screen.findByLabelText("What is this claim for?"), "Client visit");
  await userEvent.type(screen.getByLabelText("Merchant"), "Bistro 21");
  await userEvent.type(screen.getByLabelText("Amount paid (tax included)"), "56.50");
  await userEvent.click(screen.getByRole("button", { name: "Meals and entertainment" }));
  expect(screen.getByText("Receipts: $56.50")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
  await waitFor(() => expect(navigate).toHaveBeenCalled());
  const created = calls.find((c) => c.method === "POST" && c.url.endsWith("/expense-claims"));
  expect(created?.body).toMatchObject({
    title: "Client visit",
    lines: [
      {
        kind: "receipt",
        merchant: "Bistro 21",
        amount: "56.50",
        account: "c-meals",
        tax_code: "t-on",
        receipt: null,
      },
    ],
  });
  expect(calls.some((c) => c.url.endsWith(`/expense-claims/${CLAIM_ID}/submit`))).toBe(true);
  expect(navigate).toHaveBeenCalledWith(`/o/acme/purchases/expense-claims/${CLAIM_ID}`);
});

test("the server's refusal is shown", async () => {
  serve({
    status: 400,
    body: {
      code: "purchases.expense.category_missing",
      detail: "Choose a category for every receipt.",
    },
  });
  renderWithIntl(<ExpenseClaimForm org="acme" navigate={vi.fn()} />);
  await userEvent.type(await screen.findByLabelText("What is this claim for?"), "Visit");
  await userEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Choose a category for every receipt.",
  );
});

test("a claim needs a title", async () => {
  serve();
  renderWithIntl(<ExpenseClaimForm org="acme" navigate={vi.fn()} />);
  await screen.findByLabelText("What is this claim for?");
  await userEvent.click(screen.getByRole("button", { name: "Save draft" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Say what the claim is for.");
  expect(calls.some((c) => c.method === "POST")).toBe(false);
});
