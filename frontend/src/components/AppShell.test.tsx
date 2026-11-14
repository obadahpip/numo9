import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { vi } from "vitest";

import { AppShell } from "./AppShell";
import { renderWithIntl } from "@/test/intl";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeEach(() => {
  // The org switcher loads the user's organisations; these tests don't need the list.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => undefined)),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Numo9 AppShell (A-10-T05)", () => {
  it("shows the organisation's primary navigation with the current module marked", () => {
    renderWithIntl(
      <AppShell org="acme" modulePath="accounting/journals">
        <h1>Journals</h1>
      </AppShell>,
    );
    const nav = screen.getByRole("navigation", { name: "Main" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual([
      "Home",
      "Contacts",
      "Accounting",
      "Documents",
      "Settings",
    ]);
    expect(within(nav).getByRole("link", { name: "Accounting" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "Settings" })).toHaveAttribute(
      "href",
      "/o/acme/settings/general",
    );
  });

  it("builds breadcrumbs from the organisation and the module", () => {
    renderWithIntl(
      <AppShell org="acme" modulePath="accounting/journals">
        <p>body</p>
      </AppShell>,
    );
    const trail = screen.getByRole("navigation", { name: "Breadcrumbs" });
    expect(within(trail).getByRole("link", { name: "acme" })).toHaveAttribute(
      "href",
      "/o/acme/home",
    );
    expect(within(trail).getByText("Journals")).toHaveAttribute("aria-current", "page");
  });

  it("reads Organisation / Settings / <section> on a settings page (A-05-T10)", () => {
    renderWithIntl(
      <AppShell org="acme" modulePath="settings/lock-dates">
        <p>body</p>
      </AppShell>,
    );
    const trail = screen.getByRole("navigation", { name: "Breadcrumbs" });
    expect(
      within(trail)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["acme", "Settings", "Lock dates"]);
    expect(within(trail).getByRole("link", { name: "Settings" })).toHaveAttribute(
      "href",
      "/o/acme/settings/general",
    );
    expect(within(trail).getByText("Lock dates")).toHaveAttribute("aria-current", "page");
    // A settings page is not a module: no gear.
    expect(screen.queryByRole("link", { name: /settings$/ })).toBeNull();
  });

  it.each([
    ["contacts", "Contacts settings", "/o/acme/settings/custom-fields"],
    ["accounting/chart-of-accounts", "Chart of accounts settings", "/o/acme/settings/general"],
    ["accounting/journals", "Journals settings", "/o/acme/settings/lock-dates"],
  ])("the %s gear opens its own settings section (gap-03)", (modulePath, name, href) => {
    renderWithIntl(
      <AppShell org="acme" modulePath={modulePath}>
        <p>body</p>
      </AppShell>,
    );
    expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
  });

  it("shows no gear on a module without a settings section", () => {
    renderWithIntl(
      <AppShell org="acme" modulePath="home">
        <p>body</p>
      </AppShell>,
    );
    expect(document.querySelector("[data-module-settings]")).toBeNull();
  });

  it("labels every control from the en-CA catalogue", async () => {
    const user = userEvent.setup();
    renderWithIntl(
      <AppShell org="acme" modulePath="home">
        <p>body</p>
      </AppShell>,
    );
    expect(screen.getByRole("link", { name: "Skip to content" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Numo9 home" })).toHaveAttribute(
      "href",
      "/o/acme/home",
    );
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open navigation" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Account menu" }));
    expect(screen.getByRole("menuitem", { name: "Organisation settings" })).toHaveAttribute(
      "href",
      "/o/acme/settings/general",
    );
  });

  it("outside an organisation renders the shell without module links", () => {
    renderWithIntl(
      <AppShell>
        <p>body</p>
      </AppShell>,
    );
    expect(within(screen.getByRole("navigation", { name: "Main" })).queryAllByRole("link")).toEqual(
      [],
    );
    expect(screen.getByRole("link", { name: "Numo9 home" })).toHaveAttribute("href", "/");
  });
});
