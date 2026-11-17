import { screen, within } from "@testing-library/react";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { PlatformOrganisationDetail } from "./api";
import { OrganisationDetailScreen } from "./OrganisationDetailScreen";

/**
 * U-06-T04 — organisation detail in the console (subscription timeline, users, practices
 * assigned, audit). Acceptance: shows the state history — trial started, each status change and
 * the conversion, oldest first, in the organisation's time zone.
 */

const DETAIL: PlatformOrganisationDetail = {
  id: "org-1",
  name: "Maple Leaf Supply Ltd.",
  status: "active",
  is_demo: false,
  province: "ON",
  time_zone: "America/Toronto",
  created_at: "2026-10-02T14:00:00Z",
  subscription: {
    status: "active",
    reason: "",
    package: "growth",
    interval: "month",
    current_period_end: "2026-12-02T05:00:00Z",
    founding: false,
  },
  timeline: [
    { at: "2026-10-02T14:00:00Z", kind: "trial_started", detail: "" },
    { at: "2026-10-02T14:00:01Z", kind: "subscribed", detail: "trialing" },
    { at: "2026-10-20T16:00:00Z", kind: "status", detail: "trialing → active" },
    { at: "2026-10-20T16:00:00Z", kind: "converted", detail: "" },
  ],
  users: [
    {
      id: "u1",
      name: "Dana Lee",
      email: "dana@maple.ca",
      role: "owner",
      last_login: "2026-11-17T13:00:00Z",
    },
  ],
  practices: [
    { id: "p1", name: "Abuodeh CPA", role: "full_service", active: true, staff_count: 2 },
  ],
  recent_events: [
    {
      at: "2026-11-17T13:05:00Z",
      action: "contacts.contact.created",
      actor: "Dana Lee",
      record: "Cedar Roofing Co.",
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

it("shows the subscription history, users, practices and audit events", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(DETAIL), { headers: { "Content-Type": "application/json" } }),
    ),
  );
  const { container } = renderWithIntl(<OrganisationDetailScreen id="org-1" />);
  expect(await screen.findByRole("heading", { name: "Maple Leaf Supply Ltd." })).toBeVisible();
  const items = within(container.querySelector("[data-timeline]") as HTMLElement).getAllByRole(
    "listitem",
  );
  expect(items.map((item) => item.getAttribute("data-kind"))).toEqual([
    "trial_started",
    "subscribed",
    "status",
    "converted",
  ]);
  expect(items[0]).toHaveTextContent("2 Oct 2026");
  expect(items[0]).toHaveTextContent("Free trial started");
  expect(items[2]).toHaveTextContent("Status changed: trialing → active");
  expect(items[3]).toHaveTextContent("Trial converted — first payment");
  expect(screen.getByText(/Dana Lee · dana@maple.ca · role: owner/)).toBeVisible();
  expect(screen.getByText(/Abuodeh CPA — full_service, 2 staff assigned/)).toBeVisible();
  expect(screen.getByText(/contacts.contact.created · Cedar Roofing Co./)).toBeVisible();
  await expectNoAxeViolations(container);
});
