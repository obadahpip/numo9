import { describe, expect, it } from "vitest";

import { attributionFrom } from "./attribution";

describe("attributionFrom (U-08-T07)", () => {
  it("reads UTM parameters, referral source and promo code", () => {
    expect(
      attributionFrom(
        "?utm_source=newsletter&utm_medium=email&utm_campaign=founding-1000&ref=friend&promo=FOUNDING25",
        "https://numo9.ca/pricing",
      ),
    ).toEqual({
      utm_source: "newsletter",
      utm_medium: "email",
      utm_campaign: "founding-1000",
      referral_source: "friend",
      promo_code: "FOUNDING25",
      referrer: "https://numo9.ca/pricing",
    });
  });

  it("prefers the long parameter names and skips empty values", () => {
    expect(attributionFrom("?referral_source=CPA&ref=x&promo_code=A&utm_term=%20")).toEqual({
      referral_source: "CPA",
      promo_code: "A",
    });
  });

  it("returns nothing for a plain link", () => {
    expect(attributionFrom("", "")).toEqual({});
  });
});
