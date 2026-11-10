import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { OrgSwitcher, type OrgSwitcherProps } from "./OrgSwitcher";
import { manyOrganisations, sampleOrganisations, switcherLabels } from "./fixtures";

const maple = sampleOrganisations[0]!;

function setup(overrides: Partial<OrgSwitcherProps> = {}) {
  const onNavigate = vi.fn();
  const user = userEvent.setup();
  render(
    <OrgSwitcher
      labels={switcherLabels}
      active={maple}
      organisations={sampleOrganisations}
      recentIds={["org-maple", "org-north", "org-bay"]}
      hrefFor={(org) => `/o/${org.id}/contacts`}
      onNavigate={onNavigate}
      directoryHref="/p/profitex/directory"
      {...overrides}
    />,
  );
  return { user, onNavigate, button: screen.getByRole("button", { name: /Switch organisation/ }) };
}

describe("OrgSwitcher (A-01-T14)", () => {
  it("shows the active organisation and the practice badge in the header button", () => {
    const { button } = setup();
    expect(button).toHaveAccessibleName("Switch organisation Maple Leaf Supply Ltd. via Profitex");
    expect(within(button).getByText("via Profitex")).toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("omits the badge for a direct member", () => {
    const { button } = setup({ active: { id: "org-prairie", name: "Prairie Wheat Co-op" } });
    expect(button).toHaveAccessibleName("Switch organisation Prairie Wheat Co-op");
  });

  it("opens with the search box focused and the recent organisations listed", async () => {
    const { user, button } = setup();
    await user.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    const search = screen.getByRole("combobox", { name: "Search organisations" });
    expect(search).toHaveFocus();
    const list = screen.getByRole("listbox", { name: "Recent" });
    expect(
      within(list)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual([
      "Maple Leaf Supply Ltd.via ProfitexCurrent",
      "Northern Lights Bakery Inc.via Profitex",
      "Bay Street Dental Professional Corp.via Profitex",
    ]);
    expect(screen.getByRole("link", { name: "Open directory" })).toHaveAttribute(
      "href",
      "/p/profitex/directory",
    );
  });

  it("caps the recent list at 5", async () => {
    const { user, button } = setup({ recentIds: sampleOrganisations.map((o) => o.id) });
    await user.click(button);
    expect(screen.getAllByRole("option")).toHaveLength(5);
  });

  it("filters by search and opens the highlighted organisation with the keyboard", async () => {
    const { user, button, onNavigate } = setup();
    await user.click(button);
    await user.keyboard("bay");
    const list = screen.getByRole("listbox", { name: "Results" });
    expect(within(list).getAllByRole("option")).toHaveLength(1);
    await user.keyboard("{Enter}");
    expect(onNavigate).toHaveBeenCalledWith(
      "/o/org-bay/contacts",
      expect.objectContaining({ id: "org-bay" }),
    );
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("moves the highlight with the arrow keys (wrapping) and tracks aria-activedescendant", async () => {
    const { user, button, onNavigate } = setup();
    await user.click(button);
    const search = screen.getByRole("combobox");
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowDown}");
    expect(search).toHaveAttribute("aria-activedescendant", options[1]!.id);
    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(search).toHaveAttribute("aria-activedescendant", options[2]!.id);
    await user.keyboard("{Enter}");
    expect(onNavigate).toHaveBeenCalledWith("/o/org-bay/contacts", expect.anything());
  });

  it("opens an organisation on click; choosing the active one only closes", async () => {
    const { user, button, onNavigate } = setup();
    await user.click(button);
    await user.click(screen.getByRole("option", { name: /Northern Lights/ }));
    expect(onNavigate).toHaveBeenCalledWith("/o/org-north/contacts", expect.anything());
    await user.click(button);
    await user.click(screen.getByRole("option", { name: /Maple Leaf/ }));
    expect(onNavigate).toHaveBeenCalledTimes(1);
  });

  it("is accent-insensitive and reports no results", async () => {
    const { user, button } = setup();
    await user.click(button);
    await user.keyboard("quebec");
    expect(screen.getByRole("option", { name: /Érable Québec/ })).toBeInTheDocument();
    await user.clear(screen.getByRole("combobox"));
    await user.keyboard("zzz");
    expect(screen.queryAllByRole("option")).toHaveLength(0);
    expect(screen.getByText(/No organisations match/)).toBeInTheDocument();
  });

  it("caps search results for 2,000 organisations and says how many matched", async () => {
    const orgs = manyOrganisations(2000);
    const { user, button } = setup({ organisations: orgs, active: orgs[0]!, maxResults: 20 });
    await user.click(button);
    await user.keyboard("maple");
    expect(screen.getAllByRole("option")).toHaveLength(20);
    expect(
      screen.getByText("Showing 20 of 250. Refine your search or open the directory."),
    ).toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the button", async () => {
    const { user, button } = setup();
    await user.click(button);
    await user.keyboard("{Escape}");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
    expect(screen.getByRole("dialog", { hidden: true })).not.toBeVisible();
  });

  it("opens with ArrowDown from the button", async () => {
    const { user, button } = setup();
    button.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("combobox")).toHaveFocus();
  });

  it("closes on a click outside", async () => {
    const { user, button } = setup();
    await user.click(button);
    await user.click(document.body);
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("shows loading and error states with retry", async () => {
    const onRetry = vi.fn();
    const { user, button } = setup({ status: "error", organisations: [], onRetry });
    await user.click(button);
    expect(screen.getByRole("alert")).toHaveTextContent("Organisations couldn't be loaded.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("hides Open directory when the user has no practice", async () => {
    const { user, button } = setup({ directoryHref: undefined, status: "loading" });
    await user.click(button);
    expect(screen.getByRole("status")).toHaveTextContent("Loading organisations…");
    expect(screen.queryByRole("link", { name: "Open directory" })).toBeNull();
  });
});
