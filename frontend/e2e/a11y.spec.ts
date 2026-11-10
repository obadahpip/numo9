import { expect, test } from "@playwright/test";

import { auditLabels, blocking, describeFindings, runAxe } from "../../packages/ui/e2e/a11y";
import { GAP_02_PATHS } from "./gap-02.paths";

/**
 * A-10-T19 — accessibility of every Phase 0 route (Phase 0 plan §3.6 "Automated a11y"; gap-60):
 * axe-core (WCAG 2.0/2.1 A + AA, best practices, colour contrast, landmarks) with
 * 0 serious/critical violations, plus the hidden-label audit, at desktop and phone width and
 * with the navigation drawer open. The component stories are covered by
 * packages/ui/e2e/a11y.spec.ts.
 */
const ORG_ROUTES = [
  ...new Set(GAP_02_PATHS.map((p) => p.final).filter((f) => f.startsWith("/o/"))),
];
const ROUTES = ["/", ...ORG_ROUTES, "/o/acme/no-such-screen"];
const WIDTHS = [1280, 360] as const;

test.describe("a11y Phase 0 routes", () => {
  test("every Phase 0 organisation route is checked", () => {
    expect(ORG_ROUTES.length).toBeGreaterThanOrEqual(8);
  });

  for (const width of WIDTHS) {
    test.describe(`${width} px`, () => {
      test.use({ viewport: { width, height: 800 } });

      for (const route of ROUTES) {
        test(`${route}`, async ({ page }) => {
          await page.goto(route);
          await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

          const findings = await runAxe(page);
          for (const f of findings.filter((x) => !blocking([x]).length)) {
            test
              .info()
              .annotations.push({ type: `axe ${f.impact}`, description: `${f.id}: ${f.help}` });
          }
          expect(blocking(findings), describeFindings(blocking(findings))).toEqual([]);
          expect(await auditLabels(page)).toEqual([]);
        });
      }
    });
  }

  test.describe("navigation drawer (360 px)", () => {
    test.use({ viewport: { width: 360, height: 800 } });

    test("open drawer has no serious violations or leaked labels", async ({ page }) => {
      await page.goto("/o/acme/accounting/journals");
      await page.getByRole("button", { name: "Open navigation" }).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      const findings = blocking(await runAxe(page));
      expect(findings, describeFindings(findings)).toEqual([]);
      expect(await auditLabels(page)).toEqual([]);
    });
  });

  test("skip link is hidden until focused, then visible", async ({ page }) => {
    await page.goto("/o/acme/home");
    const skip = page.getByRole("link", { name: "Skip to content" });
    expect(await auditLabels(page)).toEqual([]);
    await page.keyboard.press("Tab");
    await expect(skip).toBeFocused();
    const box = await skip.boundingBox();
    expect(box!.width).toBeGreaterThan(20);
  });
});
