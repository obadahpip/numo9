import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { GoToOrganisation, isGoToShortcut } from "./GoToOrganisation";

/** V-01-T13 — Ctrl/⌘+K "Go to organisation", on the directory's search. */

const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";
const MAPLE = "11111111-0000-4000-8000-000000000000";
const RIDGE = "22222222-0000-4000-8000-000000000000";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mockSearch() {
  const urls: URL[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), "http://numo9.test");
    urls.push(url);
    return json({
      practice: { id: PRACTICE, name: "Abuodeh CPA" },
      count: 2,
      total: 2000,
      page: 1,
      page_size: 8,
      pages: 1,
      columns: ["bn", "province", "package", "status"],
      results: [
        {
          id: MAPLE,
          name: "Maple Leaf Supply Ltd.",
          bn: "123456782",
          province: "ON",
          status: "paid",
        },
        {
          id: RIDGE,
          name: "Maple Ridge Dental",
          bn: "123456109",
          province: "BC",
          status: "trial",
          trial_days_left: 12,
        },
      ],
    });
  });
  return urls;
}

afterEach(() => vi.restoreAllMocks());

describe("GoToOrganisation (V-01-T13)", () => {
  it("recognises Ctrl+K and ⌘+K only", () => {
    expect(isGoToShortcut({ key: "k", ctrlKey: true, metaKey: false })).toBe(true);
    expect(isGoToShortcut({ key: "K", ctrlKey: false, metaKey: true })).toBe(true);
    expect(isGoToShortcut({ key: "k", ctrlKey: false, metaKey: false })).toBe(false);
  });

  it("Ctrl+K opens it; typing searches the directory; ↓ + Enter opens; Esc closes", async () => {
    const urls = mockSearch();
    const navigate = vi.fn();
    const user = userEvent.setup();
    renderWithIntl(<GoToOrganisation practice={PRACTICE} navigate={navigate} />);
    await user.keyboard("{Control>}k{/Control}");
    const dialog = await screen.findByRole("dialog", { name: "Go to organisation" });
    const box = within(dialog).getByRole("combobox", {
      name: "Organisation name, BN, owner or tag",
    });
    await user.type(box, "123 456");
    expect(await within(dialog).findByText("2 results")).toBeInTheDocument();
    const query = urls.at(-1)!.searchParams;
    expect(query.get("q")).toBe("123 456");
    expect(query.get("page_size")).toBe("8");
    expect(query.get("facets")).toBe("0");
    const options = within(dialog).getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    expect(options[0]!.querySelector("mark")?.textContent).toBe("123 456");
    expect(within(options[1]!).getByText("Trial 12 d")).toBeInTheDocument();
    await expectNoAxeViolations(document.body);
    await user.keyboard("{ArrowDown}");
    expect(box).toHaveAttribute("aria-activedescendant", options[1]!.id);
    await user.keyboard("{Enter}");
    expect(navigate).toHaveBeenCalledWith(`/o/${RIDGE}/home`);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("Ctrl/⌘+Enter opens the organisation in a new tab", async () => {
    mockSearch();
    const openTab = vi.fn();
    const user = userEvent.setup();
    renderWithIntl(<GoToOrganisation practice={PRACTICE} openTab={openTab} />);
    await user.keyboard("{Meta>}k{/Meta}");
    await user.type(await screen.findByRole("combobox"), "maple");
    await screen.findByText("2 results");
    await user.keyboard("{Control>}{Enter}{/Control}");
    expect(openTab).toHaveBeenCalledWith(`/o/${MAPLE}/home`);
  });

  it("Esc closes; the directory link is there", async () => {
    mockSearch();
    const user = userEvent.setup();
    renderWithIntl(<GoToOrganisation practice={PRACTICE} />);
    await user.keyboard("{Control>}k{/Control}");
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("link", { name: "Open the directory" })).toHaveAttribute(
      "href",
      `/p/${PRACTICE}/directory`,
    );
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
