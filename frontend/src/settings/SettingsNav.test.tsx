import { screen, within } from "@testing-library/react";

import { SettingsLayout } from "./SettingsLayout";
import { SettingsNav } from "./SettingsNav";
import { ORG_MODULES, findOrgModule, settingsSections } from "@/routing/routes";
import { renderWithIntl } from "@/test/intl";

const SECTIONS = [
  ["General", "/o/acme/settings/general"],
  ["Tax registrations", "/o/acme/settings/registrations"],
  ["Lock dates", "/o/acme/settings/lock-dates"],
  ["Users and roles", "/o/acme/settings/users-roles"],
  ["Email domain", "/o/acme/settings/email-domain"],
  ["Subscription", "/o/acme/settings/subscription"],
  ["Numbering", "/o/acme/settings/numbering"],
  ["Custom fields", "/o/acme/settings/custom-fields"],
  ["Audit log", "/o/acme/settings/audit-log"],
  ["Package and features", "/o/acme/settings/package-features"],
];

describe("SettingsNav (A-05-T10)", () => {
  it("deep-links every settings section in the wireframe's order", () => {
    renderWithIntl(<SettingsNav org="acme" current="settings/general" />);
    const nav = screen.getByRole("navigation", { name: "Settings sections" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((link) => [link.textContent, link.getAttribute("href")])).toEqual(SECTIONS);
  });

  it.each(SECTIONS)("marks %s as the current page on its own URL", (name, href) => {
    const section = href.replace("/o/acme/", "");
    renderWithIntl(<SettingsNav org="acme" current={section} />);
    const nav = screen.getByRole("navigation", { name: "Settings sections" });
    const current = within(nav)
      .getAllByRole("link")
      .filter((link) => link.getAttribute("aria-current") === "page");
    expect(current.map((link) => link.textContent)).toEqual([name]);
  });

  it("frames a section's screen with the navigation", () => {
    renderWithIntl(
      <SettingsLayout org="north" section="settings/numbering">
        <h1>Numbering</h1>
      </SettingsLayout>,
    );
    expect(screen.getByRole("heading", { name: "Numbering" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Numbering" })).toHaveAttribute(
      "href",
      "/o/north/settings/numbering",
    );
  });
});

describe("route registry: settings sections and module gears (gap-03)", () => {
  it("every settings section has a short name", () => {
    expect(settingsSections().length).toBe(SECTIONS.length);
    for (const section of settingsSections()) expect(section.sectionLabel).toBeDefined();
  });

  it("every module gear points to an existing settings section, never to a module", () => {
    const gears = ORG_MODULES.filter((entry) => entry.settings !== undefined);
    expect(gears.map((entry) => entry.path)).toEqual([
      "contacts",
      "accounting/chart-of-accounts",
      "accounting/journals",
    ]);
    for (const entry of gears) {
      const target = findOrgModule(entry.settings ?? "");
      expect(target?.path.startsWith("settings/"), entry.path).toBe(true);
      expect(entry.path.startsWith("settings/")).toBe(false);
    }
  });
});
