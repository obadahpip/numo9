import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { vi } from "vitest";

import { AppShell } from "./AppShell";

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
    render(
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
    render(
      <AppShell org="acme" modulePath="settings/lock-dates">
        <p>body</p>
      </AppShell>,
    );
    const trail = screen.getByRole("navigation", { name: "Breadcrumbs" });
    expect(within(trail).getByRole("link", { name: "acme" })).toHaveAttribute(
      "href",
      "/o/acme/home",
    );
    expect(within(trail).getByText("Settings: Lock dates")).toHaveAttribute("aria-current", "page");
  });

  it("labels every control from the en-CA catalogue", async () => {
    const user = userEvent.setup();
    render(
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
    render(
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
