import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AppShell, Breadcrumbs } from "./AppShell";
import { sampleShell } from "./fixtures";

function renderShell(overrides: Partial<typeof sampleShell> = {}) {
  return render(
    <AppShell {...sampleShell} {...overrides}>
      <h1>Home</h1>
    </AppShell>,
  );
}

describe("AppShell regions (A-10-T05)", () => {
  it("renders banner, main navigation, practice navigation, breadcrumbs and main", () => {
    renderShell({ orgSwitcher: <span>Maple Leaf Supply Ltd.</span>, jobTray: <span>Jobs</span> });

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Practice" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Breadcrumbs" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByText("Maple Leaf Supply Ltd.", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("Jobs")).toBeInTheDocument();
  });

  it("links the brand mark and the skip link", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "Numo9 — Home" })).toHaveAttribute(
      "href",
      "/o/maple-leaf/home",
    );
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
  });

  it("marks the current module with aria-current=page", () => {
    renderShell();
    const main = screen.getByRole("navigation", { name: "Main" });
    expect(within(main).getByRole("link", { name: "Home" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(main).getByRole("link", { name: "Contacts" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("omits empty slots", () => {
    renderShell({ practiceNav: undefined, breadcrumbs: [] });
    expect(screen.queryByRole("navigation", { name: "Practice" })).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Breadcrumbs" })).toBeNull();
    expect(document.querySelector('[data-shell="org-switcher"]')).toBeNull();
    expect(document.querySelector('[data-shell="job-tray"]')).toBeNull();
  });

  it("uses the supplied link component for every link", () => {
    const Link = ({
      href,
      ...props
    }: { href: string } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
      <a data-router-link="" href={href} {...props} />
    );
    renderShell({ linkComponent: Link });
    const main = screen.getByRole("navigation", { name: "Main" });
    for (const link of within(main).getAllByRole("link")) {
      expect(link).toHaveAttribute("data-router-link");
    }
  });
});

describe("notification bell", () => {
  it("is named by the app label and shows the count", async () => {
    const onOpen = vi.fn();
    renderShell({ notifications: { label: "Notifications, 3 unread", count: 3, onOpen } });
    const bell = screen.getByRole("button", { name: "Notifications, 3 unread" });
    expect(bell).toHaveTextContent("3");
    await userEvent.click(bell);
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("caps the badge at 99+ and hides it at zero", () => {
    const { rerender } = renderShell({ notifications: { label: "Notifications", count: 120 } });
    expect(screen.getByRole("button", { name: "Notifications" })).toHaveTextContent("99+");
    rerender(
      <AppShell {...sampleShell} notifications={{ label: "Notifications", count: 0 }}>
        <p>x</p>
      </AppShell>,
    );
    expect(screen.getByRole("button", { name: "Notifications" })).toHaveTextContent("");
  });
});

describe("mobile navigation drawer", () => {
  it("opens and closes with the menu button; Escape returns focus", async () => {
    const user = userEvent.setup();
    renderShell();
    const toggle = screen.getByRole("button", { name: "Open navigation" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.click(toggle);
    const dialog = screen.getByRole("dialog", { name: "Navigation" });
    expect(screen.getByRole("button", { name: "Close navigation" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(within(dialog).getByRole("link", { name: "Home" })).toHaveFocus();
    expect(within(dialog).getByRole("link", { name: "Directory" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Open navigation" })).toHaveFocus();
  });

  it("closes after a link is chosen", async () => {
    const user = userEvent.setup();
    renderShell({
      linkComponent: ({ href, onClick, ...p }) => (
        <a
          href={href}
          {...p}
          onClick={(e) => {
            e.preventDefault();
            onClick?.(e);
          }}
        />
      ),
    });
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("link", { name: "Contacts" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("user menu", () => {
  it("opens, moves with arrow keys, closes with Escape", async () => {
    const user = userEvent.setup();
    renderShell();
    const button = screen.getByRole("button", { name: "Account menu: Dana Lee" });
    expect(button).toHaveAttribute("aria-haspopup", "menu");

    await user.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("menu", { name: "Account menu: Dana Lee" });
    expect(within(menu).getByText("Dana Lee")).toBeInTheDocument();
    const items = within(menu).getAllByRole("menuitem");
    expect(items.map((i) => i.textContent)).toEqual(["Profile", "Preferences", "Log out"]);
    expect(items[0]).toHaveFocus();

    await user.keyboard("{ArrowDown}");
    expect(items[1]).toHaveFocus();
    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(items[2]).toHaveFocus(); // wraps
    await user.keyboard("{Home}");
    expect(items[0]).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(button).toHaveFocus();
  });

  it("runs an action item and closes on outside click", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderShell({
      user: { ...sampleShell.user, items: [{ id: "logout", label: "Log out", onSelect }] },
    });

    await user.click(screen.getByRole("button", { name: "Account menu: Dana Lee" }));
    await user.click(screen.getByRole("menuitem", { name: "Log out" }));
    expect(onSelect).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Account menu: Dana Lee" }));
    await user.click(screen.getByRole("main"));
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("falls back to an icon when there are no initials", () => {
    renderShell({ user: { label: "Account menu", items: [] } });
    const button = screen.getByRole("button", { name: "Account menu" });
    expect(button.querySelector("svg")).not.toBeNull();
  });
});

describe("Breadcrumbs", () => {
  it("links every crumb but the last, which is the current page", () => {
    render(
      <Breadcrumbs
        label="Breadcrumbs"
        crumbs={[
          { label: "Maple Leaf Supply Ltd.", href: "/o/maple-leaf/home" },
          { label: "Accounting", href: "/o/maple-leaf/accounting/chart-of-accounts" },
          { label: "Chart of accounts" },
        ]}
      />,
    );
    expect(screen.getByRole("link", { name: "Maple Leaf Supply Ltd." })).toBeInTheDocument();
    expect(screen.getByText("Chart of accounts")).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("link", { name: "Chart of accounts" })).toBeNull();
  });

  it("hides leading crumbs on phones when there are more than two", () => {
    render(
      <Breadcrumbs
        label="Breadcrumbs"
        crumbs={[{ label: "A", href: "/a" }, { label: "B", href: "/b" }, { label: "C" }]}
      />,
    );
    const items = [...document.querySelectorAll("nav ol > li")];
    expect(items[0]).toHaveClass("md:hidden"); // ellipsis
    expect(items[1]).toHaveClass("hidden", "md:flex"); // "A"
    expect(items[2]).toHaveClass("flex");
  });
});
