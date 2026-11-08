import { defineConfig } from "@playwright/test";

/**
 * Playwright (S-01-T14): `gap-02` redirect crawler. Request-level tests only (no browser download);
 * browser-based E2E suites are added by later deliverables.
 *
 *   pnpm --filter @numo9/frontend run build && pnpm --filter @numo9/frontend run test:e2e
 */
const PORT = Number(process.env.E2E_PORT ?? 3100);
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  use: { baseURL: BASE_URL },
  webServer: {
    command: `pnpm exec next start --hostname 127.0.0.1 --port ${PORT}`,
    url: `${BASE_URL}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
