import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { ExpenseClaim } from "./api";
import { ExpenseClaimReview } from "./ExpenseClaimReview";
import { CLAIM_ID, claimFixture } from "./fixtures";

/**
 * E-04-T11 — the approver's view: lines with tax (claimable) and mileage tiers; Approve and Reject
 * for an approver; hidden, with the reason, for the claimant; reject needs a reason.
 */
let posts: { url: string; body: unknown }[] = [];

function serve(claim: ExpenseClaim) {
  posts = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (init?.method === "POST") {
          const body = init.body ? JSON.parse(String(init.body)) : null;
          posts.push({ url, body });
          const status = url.endsWith("/approve") ? "approved" : "rejected";
          return { body: { ...claim, status, can_approve: false, blocked: "status" } };
        }
        if (url.endsWith(`/expense-claims/${CLAIM_ID}`)) return { body: claim };
        return { status: 404, body: {} };
      }),
    ),
  );
}

test("approver sees the lines and approves", async () => {
  serve(claimFixture());
  renderWithIntl(<ExpenseClaimReview org="acme" id={CLAIM_ID} />);
  expect(await screen.findByRole("heading", { name: "Expense claim EXP-0001" })).toBeVisible();
  expect(screen.getByText("Bistro 21")).toBeVisible();
  expect(screen.getByText("Receipt: bistro.jpg")).toBeVisible();
  expect(screen.getByText("$6.50 ($3.25)")).toBeVisible();
  expect(screen.getByText("Office → Kingston, 100.0 km")).toBeVisible();
  expect(screen.getByText("100.0 km × $0.73")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(posts.map((p) => p.url.split("/").pop())).toEqual(["approve"]));
  expect(await screen.findByRole("status")).toHaveTextContent("Claim approved.");
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
});

test("Approve is hidden for the submitter, with the reason", async () => {
  serve(claimFixture({ can_approve: false, blocked: "self" }));
  renderWithIntl(<ExpenseClaimReview org="acme" id={CLAIM_ID} />);
  expect(await screen.findByText(/This is your claim/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Reject" })).toBeNull();
});

test("reject asks for a reason", async () => {
  serve(
    claimFixture({
      warnings: [
        {
          code: "purchases.expense.duplicate_receipt",
          line: "l1",
          message: "This receipt was already claimed on EXP-0007 (Ava).",
          claims: ["c7"],
        },
      ],
    }),
  );
  renderWithIntl(<ExpenseClaimReview org="acme" id={CLAIM_ID} />);
  expect(
    await screen.findByText("This receipt was already claimed on EXP-0007 (Ava)."),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Reject" }));
  const dialog = await screen.findByRole("dialog");
  const confirm = screen.getAllByRole("button", { name: "Reject" }).at(-1)!;
  expect(confirm).toBeDisabled();
  await userEvent.type(screen.getByLabelText(/Why is it rejected/), "Folio missing");
  await userEvent.click(confirm);
  await waitFor(() => expect(posts[0]?.body).toEqual({ reason: "Folio missing" }));
  expect(dialog).toBeDefined();
});
