import { expect, test, type Page } from "@playwright/test";

/**
 * A-01-T14 acceptance: the org switcher shows the active organisation and practice badge, lists
 * the recent organisations, searches, links to the directory, and switching keeps the equivalent
 * route. `GET /api/v1/me/organisations` is answered with fixture data (A-01-T13 response shape).
 */
const MAPLE = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const NORTH = "0b1c2d3e-4f50-4617-8899-aabbccddeeff";
const ERABLE = "5a6b7c8d-9e0f-4a1b-8c2d-3e4f5a6b7c8d";
const PROFITEX = "9e8d7c6b-5a49-4382-9170-6f5e4d3c2b1a";

const viaProfitex = [
  {
    practice_id: PROFITEX,
    practice_name: "Profitex",
    practice_role: "staff",
    assignment_role: "full_service",
    assigned_staff: true,
  },
];

const ORGANISATIONS = [
  { id: MAPLE, name: "Maple Leaf Supply Ltd." },
  { id: NORTH, name: "Northern Lights Bakery Inc." },
  { id: ERABLE, name: "Érable Québec Rénovations" },
].map((org) => ({
  ...org,
  status: "active",
  time_zone: "America/Toronto",
  membership: null,
  via_practices: viaProfitex,
}));

async function mockOrganisations(page: Page) {
  await page.route("**/api/v1/me/organisations", (route) => route.fulfill({ json: ORGANISATIONS }));
}

const switcherButton = (page: Page) =>
  page.getByRole("banner").getByRole("button", { name: /Switch organisation/ });

for (const width of [360, 1440]) {
  test.describe(`org switcher at ${width} px`, () => {
    test.use({ viewport: { width, height: 900 } });

    test("switching keeps the equivalent route", async ({ page }) => {
      await mockOrganisations(page);
      await page.goto(`/o/${MAPLE}/settings/lock-dates`);

      const button = switcherButton(page);
      await expect(button).toHaveAccessibleName(
        "Switch organisation Maple Leaf Supply Ltd. via Profitex",
      );
      await expect(button.getByText("via Profitex")).toBeVisible();

      await button.click();
      const search = page.getByRole("combobox", { name: "Search organisations" });
      await expect(search).toBeFocused();
      await search.fill("quebec");
      await page.keyboard.press("Enter");

      await expect(page).toHaveURL(`/o/${ERABLE}/settings/lock-dates`);
      await expect(switcherButton(page)).toHaveAccessibleName(
        "Switch organisation Érable Québec Rénovations via Profitex",
      );
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("Settings: Lock dates");
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth),
      ).toBeLessThanOrEqual(0);
    });
  });
}

test("recent organisations, Open directory and the current-organisation cookie", async ({
  page,
  context,
}) => {
  await mockOrganisations(page);
  await page.goto(`/o/${NORTH}/contacts`);
  await expect(switcherButton(page)).toContainText("Northern Lights Bakery Inc.");
  await page.goto(`/o/${MAPLE}/contacts`);
  await expect(switcherButton(page)).toContainText("Maple Leaf Supply Ltd.");

  await switcherButton(page).click();
  const recent = page.getByRole("listbox", { name: "Recent" });
  await expect(recent.getByRole("option")).toHaveText([
    /Maple Leaf Supply Ltd\..*Current/,
    /Northern Lights Bakery Inc\./,
  ]);
  await expect(page.getByRole("link", { name: "Open directory" })).toHaveAttribute(
    "href",
    `/p/${PROFITEX}/directory`,
  );

  // Click an option: contacts stays contacts.
  await recent.getByRole("option", { name: /Northern Lights/ }).click();
  await expect(page).toHaveURL(`/o/${NORTH}/contacts`);

  const cookies = await context.cookies();
  expect(cookies.find((cookie) => cookie.name === "numo9_org")?.value).toBe(NORTH);
  // The redirect map now sends legacy URLs without an organisation to the one last opened.
  await page.goto("/dashboard");
  await expect(page).toHaveURL((url) => url.pathname === `/o/${NORTH}/home`);
});

test("keyboard: open, arrow, Enter; Escape returns focus", async ({ page }) => {
  await mockOrganisations(page);
  await page.goto(`/o/${MAPLE}/accounting/journals`);
  await expect(switcherButton(page)).toContainText("Maple Leaf Supply Ltd.");
  await switcherButton(page).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("combobox")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(switcherButton(page)).toBeFocused();

  await page.keyboard.press("ArrowDown");
  await page.keyboard.type("bakery");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(`/o/${NORTH}/accounting/journals`);
});
