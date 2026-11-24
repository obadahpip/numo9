import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * D-03a-T15 — invoice email composer: the defaults fill the form, the PDF preview opens beside
 * it, Send posts the email and the send is listed with "Not viewed yet"; axe clean. The send
 * itself (PDF attached, logged, view tracking, bounces): backend/tests/test_invoice_email.py.
 */
const ORG = "acme";
const ID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d";

test.use({ viewport: { width: 1440, height: 900 } });

test("compose, preview the PDF and send an invoice", async ({ page }) => {
  await mockCsrf(page);
  const sends: Record<string, unknown>[] = [];
  const posted: unknown[] = [];
  await page.route(`**/api/v1/o/${ORG}/invoices/${ID}/email`, (r) => {
    if (r.request().method() === "POST") {
      const body = r.request().postDataJSON() as { to: string[]; subject: string };
      posted.push(body);
      const row = {
        id: "s1",
        recipients: body.to,
        subject: body.subject,
        language: "en-ca",
        file_name: "invoice-INV-0001.pdf",
        sent_at: "2026-06-16T14:00:00Z",
        sent_by: "Sam Patel",
        viewed_at: null,
      };
      sends.push(row);
      return r.fulfill({ status: 201, json: row });
    }
    return r.fulfill({
      json: {
        to: ["ap@cedar.ca"],
        subject: "Invoice INV-0001 from Maple Leaf Supply Ltd.",
        message: "Hello,\n\nHere is invoice INV-0001 for $339.00 CAD.",
        language: "en-ca",
        file_name: "invoice-INV-0001.pdf",
        sendable: true,
        sent_at: null,
        viewed_at: null,
        sends,
      },
    });
  });
  await page.route(`**/api/v1/o/${ORG}/invoices/${ID}/pdf`, (r) =>
    r.fulfill({ contentType: "application/pdf", body: "%PDF-1.4\n%%EOF\n" }),
  );
  await page.goto(`/o/${ORG}/sales/invoices/${ID}/email`);
  await expect(page.getByLabel("To")).toHaveValue("ap@cedar.ca");
  await expect(page.getByText("Attached: invoice-INV-0001.pdf")).toBeVisible();
  await page.getByRole("button", { name: "Preview PDF" }).click();
  await expect(page.getByTitle("Invoice PDF preview")).toBeVisible();
  await expectAccessible(page);

  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Invoice sent to ap@cedar.ca.")).toBeVisible();
  await expect(page.getByText("Not viewed yet")).toBeVisible();
  expect(posted).toEqual([
    {
      to: ["ap@cedar.ca"],
      subject: "Invoice INV-0001 from Maple Leaf Supply Ltd.",
      message: "Hello,\n\nHere is invoice INV-0001 for $339.00 CAD.",
    },
  ]);
});
