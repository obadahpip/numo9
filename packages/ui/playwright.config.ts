import { defineConfig } from "@playwright/test";

/**
 * Browser checks of @numo9/ui against the built Storybook (A-10-T19 axe + gap-60 label audit on
 * every story, A-10-T18 visual regression, A-10-T10: DataGrid 10,000 rows at
 * 60 fps; keyboard paths that need real layout). Build first:
 *   pnpm --filter @numo9/ui run build-storybook && pnpm --filter @numo9/ui run test:e2e
 */
const PORT = Number(process.env.UI_E2E_PORT ?? 6107);

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
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
    baseURL: `http://127.0.0.1:${PORT}`,
    browserName: "chromium",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
  },
  webServer: {
    command: `node scripts/serve-static.mjs storybook-static ${PORT}`,
    url: `http://127.0.0.1:${PORT}/iframe.html`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
