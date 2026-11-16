import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * A-07-T10 — Settings → Email domain: copyable DNS cards and a live checker.
 * Acceptance: the status flips to verified — the page checks the records again on its own
 * (every 20 s while not verified); once the API reports every record found, the badge says
 * Verified, each card shows ✓ and the change is announced. Also: set-up form with the server's
 * error, copy buttons, plain-language fixes for missing / wrong records, remove, axe clean.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}/email-domains`;
const ID = "33333333-3333-4333-8333-333333333333";

type Status = "unchecked" | "ok" | "missing" | "wrong";

function domain(statuses: [Status, Status, Status, Status], overall: string, label: string) {
  const kinds = [
    ["spf", "SPF", "TXT", "refined.ca", "v=spf1 include:spf.numo9.ca ~all"],
    ["dkim", "DKIM", "TXT", "pm202611._domainkey.refined.ca", "v=DKIM1; k=rsa; p=MIGfMA0G"],
    ["dmarc", "DMARC", "TXT", "_dmarc.refined.ca", "v=DMARC1; p=quarantine; adkim=r; aspf=r"],
    ["return_path", "Return path", "CNAME", "pm-bounces.refined.ca", "pm.mtasv.net"],
  ] as const;
  return {
    id: ID,
    domain: "refined.ca",
    from_local_part: "billing",
    from_address: "billing@refined.ca",
    provider: "local",
    status: overall,
    status_label: label,
    verified_at: overall === "verified" ? new Date().toISOString() : null,
    last_checked_at: null,
    created_at: new Date().toISOString(),
    records: kinds.map(([kind, kind_label, record_type, host, value], i) => ({
      kind,
      kind_label,
      record_type,
      host,
      value,
      status: statuses[i],
      status_label: statuses[i],
      found: statuses[i] === "wrong" ? "v=spf1 include:_spf.google.com ~all" : "",
      checked_at: null,
    })),
  };
}

async function setup(page: Page, list: unknown[]) {
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/notifications/unread-count`, (r) =>
    r.fulfill({ json: { unread_count: 0 } }),
  );
  await page.route(API, async (r) => {
    if (r.request().method() === "POST") {
      const body = jsonBody(r);
      if (body.domain === "gmail.com") {
        return r.fulfill({
          status: 400,
          json: {
            code: "email_domain.not_yours",
            detail:
              "Emails can't be sent from gmail.com: only the domain's owner can add its DNS records. Use your organisation's own domain.",
          },
        });
      }
      return r.fulfill({
        status: 201,
        json: domain(
          ["unchecked", "unchecked", "unchecked", "unchecked"],
          "pending",
          "Waiting for DNS records",
        ),
      });
    }
    return r.fulfill({ json: { results: list } });
  });
}

test.use({
  viewport: { width: 1280, height: 1000 },
  permissions: ["clipboard-read", "clipboard-write"],
});

test("set up a domain: server errors shown, then the DNS cards", async ({ page }) => {
  await setup(page, []);
  await page.goto(`/o/${ORG}/settings/email-domain`);
  await expect(page.getByRole("heading", { level: 1, name: "Email domain" })).toBeVisible();
  await page.getByLabel("Your domain").fill("gmail.com");
  await page.getByRole("button", { name: "Set up domain" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "only the domain's owner" }),
  ).toBeVisible();
  await expect(page.getByLabel("Your domain")).toHaveAttribute("aria-invalid", "true");
  await page.getByLabel("Your domain").fill("refined.ca");
  await page.getByRole("button", { name: "Set up domain" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "refined.ca" })).toBeVisible();
  await expect(page.locator("[data-record]")).toHaveCount(4);
  await expect(page.getByText("Emails will come from billing@refined.ca")).toBeVisible();
  await expectAccessible(page);
});

test("status flips to verified through the live checker", async ({ page }) => {
  const answers = [
    domain(["ok", "missing", "missing", "missing"], "partial", "Some records are missing"),
    domain(["wrong", "ok", "ok", "ok"], "failed", "Records are wrong"),
    domain(["ok", "ok", "ok", "ok"], "verified", "Verified"),
  ];
  let checks = 0;
  await setup(page, [
    domain(["missing", "missing", "missing", "missing"], "pending", "Waiting for DNS records"),
  ]);
  await page.route(`${API}/${ID}/check`, (r) =>
    r.fulfill({ json: answers[Math.min(checks++, answers.length - 1)] }),
  );
  await page.clock.install();
  await page.goto(`/o/${ORG}/settings/email-domain`);
  const badge = page.locator("[data-domain-status]");
  await expect(badge).toHaveText("Waiting for DNS records");
  await expect(page.locator('[data-record="dkim"]')).toContainText(
    "Not found yet. Add this record at your DNS host.",
  );

  // "Check now": partial.
  await page.getByRole("button", { name: "Check now" }).click();
  await expect(badge).toHaveText("Some records are missing");
  await expect(page.locator('[data-record="spf"]')).toContainText("✓ Found and correct");

  // The live checker (every 20 s) without a click: wrong SPF, with the fix and what was found.
  await page.clock.runFor(20_500);
  await expect(badge).toHaveText("Records are wrong");
  await expect(page.locator('[data-record="spf"]')).toContainText(
    "Replace its value with the one above. Found: v=spf1 include:_spf.google.com ~all",
  );

  await page.clock.runFor(20_500);
  await expect(badge).toHaveText("Verified");
  await expect(badge).toHaveAttribute("data-domain-status", "verified");
  await expect(page.locator('[data-record-status="ok"]')).toHaveCount(4);
  await expect(page.locator("[data-verified-live]")).toHaveText(
    "Verified: your emails now go from billing@refined.ca.",
  );
  // Verified: the checker stops.
  const after = checks;
  await page.clock.runFor(60_000);
  expect(checks).toBe(after);
  await expectAccessible(page);
});

test("copy buttons copy the host and the value; remove asks first", async ({ page }) => {
  await setup(page, [
    domain(["missing", "missing", "missing", "missing"], "pending", "Waiting for DNS records"),
  ]);
  let removed = false;
  await page.route(`${API}/${ID}`, (r) => {
    removed = r.request().method() === "DELETE";
    return r.fulfill({ status: 204, body: "" });
  });
  await page.goto(`/o/${ORG}/settings/email-domain`);
  await page.getByRole("button", { name: "Copy the value of the DKIM record" }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    "v=DKIM1; k=rsa; p=MIGfMA0G",
  );
  await page.getByRole("button", { name: "Copy the host / name of the DMARC record" }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("_dmarc.refined.ca");

  await page.getByRole("button", { name: "Remove domain" }).click();
  const dialog = page.getByRole("dialog", { name: "Remove refined.ca?" });
  await dialog.getByRole("button", { name: "Remove domain" }).click();
  await expect.poll(() => removed).toBe(true);
  await expect(page.getByLabel("Your domain")).toBeVisible();
});
