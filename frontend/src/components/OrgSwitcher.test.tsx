import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetMyOrganisations, type MyOrganisation } from "@/org/myOrganisations";
import { RECENT_ORGS_KEY } from "@/org/recentOrgs";

import { OrgSwitcher } from "./OrgSwitcher";
import { renderWithIntl } from "@/test/intl";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const MAPLE = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const NORTH = "0b1c2d3e-4f50-4617-8899-aabbccddeeff";
const OWN = "c0ffee00-1111-4222-8333-444455556666";
const PROFITEX = "9e8d7c6b-5a49-4382-9170-6f5e4d3c2b1a";

const via = (name: string) => [
  {
    practice_id: PROFITEX,
    practice_name: name,
    practice_role: "practice_admin",
    assignment_role: "full_service",
    assigned_staff: true,
  },
];

const ORGS: MyOrganisation[] = [
  {
    id: MAPLE,
    name: "Maple Leaf Supply Ltd.",
    status: "active",
    time_zone: "America/Toronto",
    membership: null,
    via_practices: via("Profitex"),
  },
  {
    id: NORTH,
    name: "Northern Lights Bakery Inc.",
    status: "trial",
    time_zone: "America/Edmonton",
    membership: null,
    via_practices: via("Profitex"),
  },
  {
    id: OWN,
    name: "Obadah Consulting",
    status: "active",
    time_zone: "America/Toronto",
    membership: { role: "owner" },
    via_practices: [],
  },
];

function respond(body: unknown, ok = true) {
  return vi.fn(() =>
    Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(body) }),
  );
}

beforeEach(() => {
  resetMyOrganisations();
  localStorage.clear();
  document.cookie = "numo9_org=; Max-Age=0; Path=/";
  push.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("OrgSwitcher container (A-01-T14)", () => {
  it("shows the active organisation's name and practice badge from the API", async () => {
    const fetchMock = respond(ORGS);
    vi.stubGlobal("fetch", fetchMock);
    renderWithIntl(<OrgSwitcher org={MAPLE} modulePath="contacts" />);

    const button = screen.getByRole("button", { name: /Switch organisation/ });
    await waitFor(() =>
      expect(button).toHaveAccessibleName(
        "Switch organisation Maple Leaf Supply Ltd. via Profitex",
      ),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/me/organisations",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("shows no badge where the user is a direct member", async () => {
    vi.stubGlobal("fetch", respond(ORGS));
    renderWithIntl(<OrgSwitcher org={OWN} modulePath="home" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Switch organisation/ })).toHaveAccessibleName(
        "Switch organisation Obadah Consulting",
      ),
    );
  });

  it("records the open organisation as recent and in the current-organisation cookie", async () => {
    vi.stubGlobal("fetch", respond(ORGS));
    localStorage.setItem(RECENT_ORGS_KEY, JSON.stringify([NORTH]));
    renderWithIntl(<OrgSwitcher org={MAPLE} modulePath="contacts" />);
    await waitFor(() =>
      expect(JSON.parse(localStorage.getItem(RECENT_ORGS_KEY) ?? "[]")).toEqual([MAPLE, NORTH]),
    );
    expect(document.cookie).toContain(`numo9_org=${MAPLE}`);
  });

  it("switches to the equivalent page of the chosen organisation", async () => {
    vi.stubGlobal("fetch", respond(ORGS));
    const user = userEvent.setup();
    renderWithIntl(<OrgSwitcher org={MAPLE} modulePath="settings/lock-dates" />);
    await user.click(await screen.findByRole("button", { name: /Maple Leaf/ }));
    await user.keyboard("northern");
    await user.keyboard("{Enter}");
    expect(push).toHaveBeenCalledWith(`/o/${NORTH}/settings/lock-dates`);
  });

  it("links Open directory to the acting practice's directory", async () => {
    vi.stubGlobal("fetch", respond(ORGS));
    const user = userEvent.setup();
    renderWithIntl(<OrgSwitcher org={MAPLE} />);
    await user.click(await screen.findByRole("button", { name: /Maple Leaf/ }));
    expect(screen.getByRole("link", { name: "Open directory" })).toHaveAttribute(
      "href",
      `/p/${PROFITEX}/directory`,
    );
  });

  it("falls back to the URL segment and offers a retry when the request fails", async () => {
    const failing = respond({ detail: "boom" }, false);
    vi.stubGlobal("fetch", failing);
    const user = userEvent.setup();
    renderWithIntl(<OrgSwitcher org={MAPLE} modulePath="home" />);
    const button = screen.getByRole("button", { name: `Switch organisation ${MAPLE}` });
    await user.click(button);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Your organisations couldn't be loaded.");

    vi.stubGlobal("fetch", respond(ORGS));
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(screen.getByRole("listbox", { name: "Recent" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("option", { name: /Maple Leaf/ })).toBeInTheDocument();
  });
});
