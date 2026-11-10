import { renderHook } from "@testing-library/react";
import { createElement } from "react";

import { IntlWrapper } from "@/test/intl";

import { defineMessages, useFormatMessage } from "./index";
import { LOCALE_COOKIE, pseudoLocaleEnabled, resolveLocale } from "./locales";
import { pseudoCatalog, pseudoLocalise } from "./pseudo";

const messages = defineMessages({
  brand: { id: "common.brand", defaultMessage: "Numo9", description: "test" },
  more: {
    id: "orgSwitcher.moreResults",
    defaultMessage:
      "Showing {shown, number} of {total, number}. Refine your search or open the directory.",
    description: "test",
  },
});

describe("useFormatMessage (next-intl, A-10-T13)", () => {
  it("reads the active catalogue and formats ICU arguments for the locale", () => {
    const { result } = renderHook(() => useFormatMessage(), { wrapper: IntlWrapper });
    expect(result.current(messages.brand)).toBe("Numo9");
    expect(result.current(messages.more, { shown: 20, total: 2000 })).toBe(
      "Showing 20 of 2,000. Refine your search or open the directory.",
    );
  });

  it("formats numbers in French", () => {
    const fr = { orgSwitcher: { moreResults: "{shown, number} sur {total, number}" } };
    const { result } = renderHook(() => useFormatMessage(), {
      wrapper: ({ children }) =>
        createElement(IntlWrapper, { locale: "fr-CA", messages: fr }, children),
    });
    expect(result.current(messages.more, { shown: 20, total: 2000 })).toBe("20 sur 2 000");
  });
});

describe("resolveLocale (A-10-T13)", () => {
  it.each([
    [{ cookie: "fr-CA" }, "fr-CA"],
    [{ cookie: "fr_ca" }, "fr-CA"],
    [{ cookie: "de-DE", acceptLanguage: "fr-FR,fr;q=0.9" }, "fr-CA"],
    [{ acceptLanguage: "en-US,en;q=0.8" }, "en-CA"],
    [{ acceptLanguage: "de-DE,fr;q=0.5,en;q=0.3" }, "fr-CA"],
    [{ acceptLanguage: "es" }, "en-CA"],
    [{}, "en-CA"],
    [{ cookie: "en-XA" }, "en-CA"],
    [{ cookie: "en-XA", pseudo: true }, "en-XA"],
  ])("%j → %s", (input, expected) => {
    expect(resolveLocale(input)).toBe(expected);
  });

  it("pseudo-locale is off in production unless enabled", () => {
    expect(pseudoLocaleEnabled({ NODE_ENV: "production" })).toBe(false);
    expect(pseudoLocaleEnabled({ NODE_ENV: "production", NUMO9_PSEUDO_LOCALE: "1" })).toBe(true);
    expect(pseudoLocaleEnabled({ NODE_ENV: "development" })).toBe(true);
    expect(pseudoLocaleEnabled({ NODE_ENV: "development", NUMO9_PSEUDO_LOCALE: "0" })).toBe(false);
    expect(LOCALE_COOKIE).toBe("numo9_locale");
  });
});

describe("pseudo-locale en-XA (A-10-T13)", () => {
  it("accents letters, adds ~30 % length, brackets the text, keeps ICU arguments", () => {
    expect(pseudoLocalise("Settings")).toBe("[Šéţţîñĝš ~~~]");
    const text = pseudoLocalise("via {practice}");
    expect(text).toBe("[ṽîá {practice} ~]");
    const long = "Organisation settings";
    expect(pseudoLocalise(long).length).toBeGreaterThanOrEqual(Math.round(long.length * 1.3));
    expect(pseudoLocalise("{count, plural, one {# line} other {# lines}}")).toContain(
      "{count, plural, one {# line} other {# lines}}",
    );
  });

  it("pseudo-localises a whole nested catalogue", () => {
    expect(pseudoCatalog({ a: { b: "Home" } })).toEqual({ a: { b: "[Ĥöɱé ~~]" } });
  });
});
