import { describe, expect, it } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { DiffViewer } from "./DiffViewer";
import { auditDateTime, AuditTime } from "./time";

/**
 * A-04-T12 — times in the audit log honour the viewer's preference: 24 h, or 12 h with a.m./p.m.
 * — never "16:33PM" (gap-44: Xero's "Edited by System Generated on 5 Jan 2026 at 16:33PM").
 * Snapshots of every locale × preference, plus a sweep over every minute of a day.
 */
const AT = "2026-01-05T21:33:00Z"; // 4:33 p.m. in Toronto (EST)
const TORONTO = "America/Toronto";

describe("auditDateTime", () => {
  it("matches the snapshot for each language and preference", () => {
    const shown = Object.fromEntries(
      (["en-CA", "fr-CA"] as const).flatMap((locale) =>
        (["12h", "24h"] as const).map((time_format) => [
          `${locale} ${time_format}`,
          auditDateTime(AT, { locale, viewer: { time_format, time_zone: TORONTO } }),
        ]),
      ),
    );
    expect(shown).toMatchInlineSnapshot(`
      {
        "en-CA 12h": "5 Jan 2026, 4:33 p.m.",
        "en-CA 24h": "5 Jan 2026, 16:33",
        "fr-CA 12h": "5 janv. 2026, 4 h 33 p.m.",
        "fr-CA 24h": "5 janv. 2026, 16 h 33",
      }
    `);
  });

  it("uses the organisation's time zone", () => {
    const viewer = { time_format: "24h", time_zone: "America/Vancouver" } as const;
    expect(auditDateTime(AT, { locale: "en-CA", viewer })).toBe("5 Jan 2026, 13:33");
  });

  it("defaults by language when no preference is known", () => {
    expect(auditDateTime(AT, { locale: "en-CA" })).toBe("5 Jan 2026, 4:33 p.m.");
    expect(auditDateTime(AT, { locale: "fr-CA" })).toBe("5 janv. 2026, 16 h 33");
  });

  it("never mixes a 24-hour clock with AM/PM, at any minute of the day", () => {
    const mixed = /\b(1[3-9]|2[0-3]|00):\d{2}\s?([AaPp]\.?[Mm]\.?)/;
    for (let minute = 0; minute < 24 * 60; minute += 7) {
      const at = new Date(Date.UTC(2026, 0, 5, 5, minute)).toISOString();
      for (const locale of ["en-CA", "fr-CA"] as const) {
        for (const time_format of ["12h", "24h"] as const) {
          const text = auditDateTime(at, { locale, viewer: { time_format, time_zone: TORONTO } });
          expect(text).not.toMatch(mixed);
          if (time_format === "24h") expect(text).not.toMatch(/[ap]\.m\./i);
          else expect(text).toMatch(/[ap]\.m\./);
        }
      }
    }
  });
});

describe("AuditTime", () => {
  it("renders a <time> with the machine value and the viewer's text", () => {
    const { container } = renderWithIntl(
      <AuditTime at={AT} locale="en-CA" viewer={{ time_format: "24h", time_zone: TORONTO }} />,
    );
    expect(container.innerHTML).toMatchInlineSnapshot(
      `"<time datetime="2026-01-05T21:33:00Z" data-audit-time="">5 Jan 2026, 16:33</time>"`,
    );
  });

  it("renders a DiffViewer whose before/after are named in words", () => {
    const { container } = renderWithIntl(
      <DiffViewer
        changes={[
          { field: "amount", label: "Amount", old: "100.00", new: "120.50", masked: false },
          {
            field: "sin",
            label: "SIN",
            old: { masked: true },
            new: { masked: true },
            masked: true,
          },
        ]}
      />,
    );
    expect(container.textContent).toMatchInlineSnapshot(
      `"AmountBefore100.00After120.50SINChanged — the value is hidden for privacy"`,
    );
  });
});
