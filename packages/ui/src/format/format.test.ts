import { addDays, addMonths, endOfMonth, isoDate, todayIn } from "./dates";
import { formatDate, formatDateTime, formatMoney, formatNumber, formatTime } from "./format";
import { parseDate, parseMoney } from "./parse";

const NBSP = " ";

describe("formatMoney (A-10-T08)", () => {
  it.each([
    ["1234.56", "en-CA", "$1,234.56"],
    ["1234.56", "fr-CA", `1${NBSP}234,56${NBSP}$`],
    ["-1234.5", "en-CA", "-$1,234.50"],
    ["0", "en-CA", "$0.00"],
    ["-0.001", "en-CA", "$0.00"],
    ["1234567.89", "fr-CA", `1${NBSP}234${NBSP}567,89${NBSP}$`],
    ["1234.56", "en-XA", "$1,234.56"],
  ] as const)("%s in %s → %s", (amount, locale, expected) => {
    expect(formatMoney(amount, { locale })).toBe(expected);
  });

  it("formats decimal strings exactly (no float drift) and large amounts", () => {
    expect(formatMoney("0.30", { locale: "en-CA" })).toBe("$0.30");
    expect(formatMoney("12345678901234.56", { locale: "en-CA" })).toBe("$12,345,678,901,234.56");
    expect(formatMoney(1234.5, { locale: "en-CA" })).toBe("$1,234.50");
  });

  it("accounting negatives and foreign currencies", () => {
    expect(formatMoney("-1234.56", { locale: "en-CA", accounting: true })).toBe("($1,234.56)");
    expect(formatMoney("-1234.56", { locale: "fr-CA", accounting: true })).toBe(
      `(1${NBSP}234,56${NBSP}$)`,
    );
    expect(formatMoney("10", { locale: "en-CA", currency: "USD" })).toBe("US$10.00");
  });

  it("rejects non-amounts", () => {
    expect(() => formatMoney("12abc", { locale: "en-CA" })).toThrow(RangeError);
    expect(() => formatMoney(Number.NaN, { locale: "en-CA" })).toThrow(RangeError);
  });

  it("formatNumber", () => {
    expect(formatNumber("1234.5", { locale: "en-CA" })).toBe("1,234.5");
    expect(formatNumber("1234.5", { locale: "fr-CA" })).toBe(`1${NBSP}234,5`);
  });
});

describe("formatDate (A-10-T08): one format per locale", () => {
  it.each([
    ["2026-10-26", "en-CA", "26 Oct 2026"],
    ["2026-10-26", "fr-CA", "26 oct. 2026"],
    ["2026-01-05", "en-CA", "5 Jan 2026"],
    ["2026-09-30", "fr-CA", "30 sept. 2026"],
    ["2026-10-26", "en-XA", "26 Oct 2026"],
  ] as const)("%s in %s → %s", (date, locale, expected) => {
    expect(formatDate(date, { locale })).toBe(expected);
  });

  it("calendar dates never shift with the time zone; instants use the org time zone", () => {
    // 27 Oct 2026 02:30 UTC is 26 Oct, 10:30 p.m. in Toronto.
    const instant = new Date("2026-10-27T02:30:00Z");
    expect(formatDate(instant, { locale: "en-CA", timeZone: "America/Toronto" })).toBe(
      "26 Oct 2026",
    );
    expect(formatDate(instant, { locale: "en-CA", timeZone: "UTC" })).toBe("27 Oct 2026");
    expect(formatDate("2026-10-27", { locale: "en-CA" })).toBe("27 Oct 2026");
  });

  it("rejects invalid dates", () => {
    expect(() => formatDate("2026-02-30", { locale: "en-CA" })).toThrow(RangeError);
  });
});

describe("formatTime (A-10-T08): user 12/24 h", () => {
  const t = new Date("2026-10-26T20:33:00Z"); // 4:33 p.m. in Toronto (EDT)

  it.each([
    ["en-CA", "12h", "4:33 p.m."],
    ["en-CA", "24h", "16:33"],
    ["fr-CA", "24h", "16 h 33"],
    ["fr-CA", "12h", "4 h 33 p.m."],
  ] as const)("%s %s → %s", (locale, timeFormat, expected) => {
    expect(formatTime(t, { locale, timeFormat, timeZone: "America/Toronto" })).toBe(expected);
  });

  it("defaults: 12 h in English, 24 h in French; never '16:33PM'", () => {
    expect(formatTime(t, { locale: "en-CA" })).toBe("4:33 p.m.");
    expect(formatTime(t, { locale: "fr-CA" })).toBe("16 h 33");
    for (const locale of ["en-CA", "fr-CA"] as const)
      for (const timeFormat of ["12h", "24h"] as const)
        expect(formatTime(t, { locale, timeFormat })).not.toMatch(/1[3-9]:\d\d\s*[AP]\.?M/i);
  });

  it("midnight and noon in 12 h", () => {
    expect(formatTime("2026-10-26T04:00:00Z", { locale: "en-CA", timeFormat: "12h" })).toBe(
      "12:00 a.m.",
    );
    expect(formatTime("2026-10-26T16:00:00Z", { locale: "en-CA", timeFormat: "12h" })).toBe(
      "12:00 p.m.",
    );
  });

  it("formatDateTime", () => {
    expect(formatDateTime(t, { locale: "en-CA" })).toBe("26 Oct 2026, 4:33 p.m.");
    expect(formatDateTime(t, { locale: "fr-CA" })).toBe("26 oct. 2026, 16 h 33");
  });
});

describe("parseMoney (A-10-T08): forgiving", () => {
  it.each([
    ["1,234.5", "en-CA", "1234.50"],
    ["1234.50", "en-CA", "1234.50"],
    ["$1,234.56", "en-CA", "1234.56"],
    ["1,234", "en-CA", "1234.00"],
    ["1,5", "en-CA", "1.50"],
    ["1.234,56", "en-CA", "1234.56"],
    ["(12.00)", "en-CA", "-12.00"],
    ["-12", "en-CA", "-12.00"],
    ["12-", "en-CA", "-12.00"],
    ["−12.5", "en-CA", "-12.50"],
    [".5", "en-CA", "0.50"],
    ["CAD 99", "en-CA", "99.00"],
    ["0", "en-CA", "0.00"],
    ["-0", "en-CA", "0.00"],
    ["1 234,50", "fr-CA", "1234.50"],
    [`$1${NBSP}234,50`, "fr-CA", "1234.50"],
    [`1 234,5 $`, "fr-CA", "1234.50"],
    ["1234.5", "fr-CA", "1234.50"],
    ["1,25", "fr-CA", "1.25"],
    ["1,234,567.89", "en-CA", "1234567.89"],
  ] as const)("%j (%s) → %s", (input, locale, expected) => {
    expect(parseMoney(input, { locale })).toBe(expected);
  });

  it.each([
    ["", "en-CA"],
    ["abc", "en-CA"],
    ["12.345", "en-CA"], // 3 decimals: not silently rounded
    ["1,234", "fr-CA"], // comma is the decimal mark in French → 3 decimals
    ["1,23,4", "en-CA"],
    ["12..5", "en-CA"],
    ["1.2.3,4", "en-CA"],
    ["$", "en-CA"],
    ["12 apples", "en-CA"],
  ] as const)("rejects %j (%s)", (input, locale) => {
    expect(parseMoney(input, { locale })).toBeNull();
  });

  it("other precisions", () => {
    expect(parseMoney("1.2345", { locale: "en-CA", fractionDigits: 4 })).toBe("1.2345");
    expect(parseMoney("12", { locale: "en-CA", fractionDigits: 0 })).toBe("12");
  });
});

describe("parseDate (A-10-T08): forgiving", () => {
  const today = "2026-10-15";
  it.each([
    ["2026-10-26", "2026-10-26"],
    ["2026/10/26", "2026-10-26"],
    ["20261026", "2026-10-26"],
    ["26/10", "2026-10-26"],
    ["26/10/2026", "2026-10-26"],
    ["26-10-26", "2026-10-26"],
    ["26.10.2026", "2026-10-26"],
    ["10/26/2026", "2026-10-26"], // month first only when unambiguous
    ["3/4/2026", "2026-04-03"], // ambiguous → day first
    ["26", "2026-10-26"],
    ["oct 26", "2026-10-26"],
    ["Oct 26", "2026-10-26"],
    ["26 oct", "2026-10-26"],
    ["26 oct. 2026", "2026-10-26"],
    ["October 26, 2026", "2026-10-26"],
    ["26 octobre 2026", "2026-10-26"],
    ["1er octobre", "2026-10-01"],
    ["1st Feb 2027", "2027-02-01"],
    ["5 févr. 2026", "2026-02-05"],
    ["2026 oct 26", "2026-10-26"],
    ["sept 30", "2026-09-30"],
    ["today", "2026-10-15"],
    ["Aujourd'hui", "2026-10-15"],
    ["tomorrow", "2026-10-16"],
    ["hier", "2026-10-14"],
    ["+30", "2026-11-14"],
    ["-7", "2026-10-08"],
    ["+2w", "2026-10-29"],
    ["+1m", "2026-11-15"],
    ["+1y", "2027-10-15"],
    ["  +14  ", "2026-10-29"],
  ])("%j → %s", (input, expected) => {
    expect(parseDate(input, { locale: "en-CA", today })).toBe(expected);
  });

  it.each([
    "",
    "31/02/2026",
    "13/13",
    "oct",
    "oct 2026",
    "blue 26",
    "26 oct nov",
    "2026-13-01",
    "32",
  ])("rejects %j", (input) => {
    expect(parseDate(input, { locale: "fr-CA", today })).toBeNull();
  });

  it("leap years", () => {
    expect(parseDate("29/02/2028", { locale: "en-CA", today })).toBe("2028-02-29");
    expect(parseDate("29/02/2027", { locale: "en-CA", today })).toBeNull();
  });
});

describe("calendar-date helpers", () => {
  it("adds days and months (clamped), end of month, today in a time zone", () => {
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addMonths("2026-01-31", 1)).toBe("2026-02-28");
    expect(addMonths("2026-03-15", -3)).toBe("2025-12-15");
    expect(endOfMonth("2028-02-10")).toBe("2028-02-29");
    expect(isoDate(2026, 2, 29)).toBeNull();
    expect(todayIn("America/Toronto", new Date("2026-10-27T02:30:00Z"))).toBe("2026-10-26");
    expect(todayIn("America/Halifax", new Date("2026-10-27T02:30:00Z"))).toBe("2026-10-26");
    expect(todayIn("Europe/Helsinki", new Date("2026-10-27T02:30:00Z"))).toBe("2026-10-27");
  });
});
