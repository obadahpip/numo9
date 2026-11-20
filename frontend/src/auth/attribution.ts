/**
 * Acquisition attribution sent with the sign-up (U-08-T07): the UTM parameters, referral source
 * and promo code of the link the visitor arrived by (`?utm_source=…&ref=…&promo=…`) and the page
 * that referred them. Only non-empty values are sent; the server trims each to its column.
 */

const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"] as const;

export type Attribution = Partial<
  Record<(typeof UTM_KEYS)[number] | "referral_source" | "promo_code" | "referrer", string>
>;

export function attributionFrom(search: string, referrer = ""): Attribution {
  const params = new URLSearchParams(search);
  const out: Attribution = {};
  for (const key of UTM_KEYS) {
    const value = params.get(key)?.trim();
    if (value) out[key] = value;
  }
  const referral = (params.get("referral_source") ?? params.get("ref"))?.trim();
  if (referral) out.referral_source = referral;
  const promo = (params.get("promo_code") ?? params.get("promo"))?.trim();
  if (promo) out.promo_code = promo;
  if (referrer.trim()) out.referrer = referrer.trim();
  return out;
}

/** The current page's attribution (browser only). */
export function currentAttribution(): Attribution {
  if (typeof window === "undefined") return {};
  return attributionFrom(window.location.search, document.referrer);
}
