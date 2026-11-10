import { defineConfig } from "@playwright/test";

/**
 * Playwright: `gap-02` redirect crawler (S-01-T14, request-level), the responsive app-shell
 * suite (A-10-T05, Chromium at 360 / 768 / 1024 / 1440 px), the org switcher (A-01-T14) and the
 * locale / pseudo-locale checks (A-10-T13) and the gap-12 no-banner layout check (A-10-T17).
 * Browser once per machine:
 *   pnpm --filter @numo9/frontend exec playwright install chromium
 *
 *   pnpm --filter @numo9/frontend run build && pnpm --filter @numo9/frontend run test:e2e
 */
const PORT = Number(process.env.E2E_PORT ?? 3100);
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  forbidOnly: Boolean(process.env.CI),
  // Visual regression (A-10-T18): one Linux baseline per screenshot, no platform suffix; run
  // the @visual tests on Linux only (CI job `visual`). Small tolerance for anti-aliasing.
  snapshotPathTemplate: "{testDir}/__screenshots__/{testFilePath}/{arg}{ext}",
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
      scale: "css",
      threshold: 0.2,
      maxDiffPixels: 100,
    },
  },
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  use: {
    baseURL: BASE_URL,
    browserName: "chromium",
    // Optional local override when the pinned Playwright browser cannot be downloaded.
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
  },
  webServer: {
    command: `pnpm exec next start --hostname 127.0.0.1 --port ${PORT}`,
    url: `${BASE_URL}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    // The pseudo-locale en-XA is off in production builds unless enabled (A-10-T13 layout check).
    env: { NUMO9_PSEUDO_LOCALE: "1" },
  },
});
