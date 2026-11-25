import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { StopImpact } from "./api";
import { FilingTimeline } from "./FilingTimeline";
import { period, Q1, QUARTERLY, REG } from "./fixtures";
import { RegistrationHistory } from "./RegistrationHistory";
import { StopFilingCard } from "./StopFilingCard";

/**
 * G-03b-T10, T11 — the "Not registered" band between a stop and a restart with its markers (and
 * one still open while stopped); the history names the person; the danger zone shows the impact
 * and enables Stop filing only once the registration number is typed.
 */
const Q2 = period({ start: "2026-04-01", end: "2026-06-30", status: "filed" });
const Q1_2027 = period({ start: "2027-01-01", end: "2027-03-31" });

it("draws the Not registered band between the stop and the restart", async () => {
  const { container } = renderWithIntl(
    <FilingTimeline
      periods={[Q1, Q2, Q1_2027]}
      cycles={[QUARTERLY]}
      gaps={[{ start: "2026-07-01", end: "2026-12-31" }]}
    />,
  );
  const timeline = screen.getByRole("region", { name: "Filing periods timeline" });
  const items = [...timeline.querySelectorAll<HTMLElement>("li[data-period], li[data-gap]")];
  expect(items.map((i) => i.dataset.period ?? `gap ${i.dataset.gap}`)).toEqual([
    "2026-01-01",
    "2026-04-01",
    "gap 2026-07-01",
    "2027-01-01",
  ]);
  expect(
    within(timeline).getByRole("img", { name: "Not registered: 1 Jul 2026 – 31 Dec 2026" }),
  ).toBeVisible();
  expect(within(timeline).getByText("Stopped 30 Jun 2026")).toBeVisible();
  expect(within(timeline).getByText("Restarted 1 Jan 2027")).toBeVisible();
  await expectNoAxeViolations(container);
});

it("keeps the band open while stopped", () => {
  renderWithIntl(
    <FilingTimeline
      periods={[Q1, Q2]}
      cycles={[QUARTERLY]}
      gaps={[{ start: "2026-07-01", end: null }]}
    />,
  );
  const band = screen.getByRole("img", { name: "Not registered: From 1 Jul 2026" });
  expect(band.closest("li")?.dataset.gapEnd).toBe("");
  expect(screen.queryByText(/Restarted/)).toBeNull();
});

it("lists stops and restarts with the person", () => {
  renderWithIntl(
    <RegistrationHistory
      events={[
        {
          id: "e1",
          action: "stop",
          date: "2026-06-30",
          reason_code: "deregistration",
          reason_label: "Registration cancelled",
          reason_text: "Sold",
          frequency: "",
          by: { id: "u1", name: "Dana Lee" },
          at: "2026-07-02T14:14:00Z",
        },
      ]}
    />,
  );
  expect(
    screen.getByText(/30 Jun 2026: stopped — Registration cancelled — “Sold” — Dana Lee/),
  ).toBeVisible();
});

const IMPACT: StopImpact = {
  removed: [
    period({ start: "2026-07-01", end: "2026-09-30" }),
    period({ start: "2026-10-01", end: "2026-12-31" }),
  ],
  added: [],
  changed: [],
  periods: [Q1, Q2],
  warnings: [],
  documents: [
    {
      kind: "invoice",
      id: "i1",
      number: "INV-0043",
      date: "2026-07-15",
      total: "113.00",
      url: "/o/acme/sales/invoices/i1",
    },
  ],
  out_of_scope_default: true,
  stopped: true,
};

it("previews the impact and needs the typed registration number", async () => {
  const posts: { url: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        posts.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null });
        if (url.endsWith("/preview")) return { body: IMPACT };
        if (url.endsWith("/stop"))
          return { status: 201, body: { ...IMPACT, events: [], gaps: [] } };
        return { status: 404, body: {} };
      }),
    ),
  );
  const stopped = vi.fn();
  const user = userEvent.setup();
  renderWithIntl(
    <StopFilingCard org="acme" registration={REG} number="123456782RT0001" onStopped={stopped} />,
  );
  await user.type(screen.getByLabelText("Last day registered"), "2026-06-30");
  await user.click(screen.getByRole("button", { name: "Review the impact" }));
  expect(
    await screen.findByText("Your final return covers 1 Apr 2026 – 30 Jun 2026."),
  ).toBeVisible();
  expect(screen.getByText("2 periods after 30 Jun 2026 will be removed.")).toBeVisible();
  expect(
    screen.getByText("1 document dated after 30 Jun 2026 uses GST/HST or QST codes: review it."),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "INV-0043 (15 Jul 2026)" })).toHaveAttribute(
    "href",
    "/o/acme/sales/invoices/i1",
  );
  expect(screen.getByText("New sales after 30 Jun 2026 default to Out of scope.")).toBeVisible();
  const confirm = screen.getByRole("button", { name: "Stop filing" });
  expect(confirm).toBeDisabled();
  const typed = screen.getByLabelText(/Type the registration number/);
  await user.type(typed, "123456782RT0002");
  expect(confirm).toBeDisabled();
  await user.clear(typed);
  await user.type(typed, "123456782 RT 0001");
  expect(confirm).toBeEnabled();
  await user.click(confirm);
  await waitFor(() => expect(stopped).toHaveBeenCalled());
  expect(posts.at(-1)?.body).toEqual({
    date: "2026-06-30",
    reason_code: "deregistration",
    reason_text: "",
    confirm_number: "123456782 RT 0001",
  });
});
