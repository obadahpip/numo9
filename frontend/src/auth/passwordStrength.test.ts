import { passwordStrength, strengthScore } from "./passwordStrength";
import { apiLocale } from "./SignupFlow";

describe("passwordStrength", () => {
  it.each([
    ["", "empty"],
    ["Sh0rt!", "tooShort"],
    ["abcdefghijk", "tooShort"], // 11 characters
    ["aaaaaaaaaaaaaaaa", "fair"], // one repeated character
    ["123456789012", "fair"],
    ["lowercaseonly", "fair"],
    ["lowercase12345", "good"], // 14 characters,
    ["correct horse battery 42", "strong"],
    ["Tr0ub4dor&3xyz", "strong"],
  ])("%j → %s", (password, expected) => {
    expect(passwordStrength(password)).toBe(expected);
  });

  it("never rates below the 12-character minimum as better than too short", () => {
    expect(passwordStrength("Aa1!Aa1!Aa1")).toBe("tooShort");
    expect(strengthScore("tooShort")).toBe(1);
    expect(strengthScore("strong")).toBe(4);
  });
});

describe("apiLocale", () => {
  it.each([
    ["en-CA", "en-ca"],
    ["fr-CA", "fr-ca"],
    ["en-XA", "en-ca"],
  ])("%s → %s", (locale, api) => {
    expect(apiLocale(locale)).toBe(api);
  });
});
