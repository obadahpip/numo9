import { safeNextUrl } from "./nextUrl";

describe("safeNextUrl (no open redirect)", () => {
  it.each([
    ["/o/acme/contacts", "/o/acme/contacts"],
    ["/o/acme/contacts?view=suppliers#top", "/o/acme/contacts?view=suppliers#top"],
    [undefined, "/"],
    ["", "/"],
    ["https://evil.example/", "/"],
    ["//evil.example", "/"],
    ["/\\evil.example", "/"],
    ["javascript:alert(1)", "/"],
    ["/o/acme\n/x", "/"],
    ["/login", "/"],
    ["/login?next=/x", "/"],
    ["/reset/abc", "/"],
    ["/loginx", "/loginx"],
    [`/${"a".repeat(3000)}`, "/"],
  ])("%j → %j", (next, expected) => {
    expect(safeNextUrl(next)).toBe(expected);
  });
});
