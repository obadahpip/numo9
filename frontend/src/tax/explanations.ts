/**
 * The tax resolver's explanation keys (G-02-T02) as words — the "auto" chip's tooltip: "Ontario
 * → HST 13 %". `params.province` is the province of supply (code), `country` a country, `date` a
 * stop date (G-03b).
 */
import { defineMessages, type FormatMessage, type MessageDescriptor } from "@/i18n";

export const explanations = defineMessages({
  "tax.pos.hst": {
    id: "tax.pos.hst",
    defaultMessage: "Supplied in {province}: HST",
    description: "Tax tooltip: HST province",
  },
  "tax.pos.gst": {
    id: "tax.pos.gst",
    defaultMessage: "Supplied in {province}: GST",
    description: "Tax tooltip: GST-only province or territory",
  },
  "tax.pos.gst_qst": {
    id: "tax.pos.gstQst",
    defaultMessage: "Supplied in Quebec, QST-registered: GST and QST",
    description: "Tax tooltip",
  },
  "tax.pos.gst_pst": {
    id: "tax.pos.gstPst",
    defaultMessage: "Supplied in {province}, PST-registered: GST and PST",
    description: "Tax tooltip",
  },
  "tax.pos.gst_unregistered_qst": {
    id: "tax.pos.gstUnregisteredQst",
    defaultMessage: "Supplied in Quebec, not QST-registered: GST only",
    description: "Tax tooltip",
  },
  "tax.pos.gst_unregistered_pst": {
    id: "tax.pos.gstUnregisteredPst",
    defaultMessage: "Supplied in {province}, not registered for its PST: GST only",
    description: "Tax tooltip",
  },
  "tax.pos.export": {
    id: "tax.pos.export",
    defaultMessage: "Supplied outside Canada ({country}): zero-rated export",
    description: "Tax tooltip",
  },
  "tax.pos.import": {
    id: "tax.pos.import",
    defaultMessage: "Supplier outside Canada ({country}): out of scope",
    description: "Tax tooltip",
  },
  "tax.pos.supplier_province": {
    id: "tax.pos.supplierProvince",
    defaultMessage: "Supplier in {province}: its standard rate",
    description: "Tax tooltip",
  },
  "tax.pos.account": {
    id: "tax.pos.account",
    defaultMessage: "The account's default tax code",
    description: "Tax tooltip",
  },
  "tax.pos.item": {
    id: "tax.pos.item",
    defaultMessage: "The item's tax setting",
    description: "Tax tooltip",
  },
  "tax.pos.contact": {
    id: "tax.pos.contact",
    defaultMessage: "The contact's default tax code",
    description: "Tax tooltip",
  },
  "tax.pos.override": {
    id: "tax.pos.override",
    defaultMessage: "Chosen on this line",
    description: "Tax tooltip",
  },
  "tax.pos.none": {
    id: "tax.pos.none",
    defaultMessage: "No default: choose a tax code",
    description: "Tax tooltip",
  },
  "tax.pos.registration_stopped": {
    id: "tax.pos.registrationStopped",
    defaultMessage: "GST/HST filing stopped after {date}: out of scope",
    description: "Tax tooltip (G-03b)",
  },
});

export function explain(
  fm: FormatMessage,
  key: string,
  params: Record<string, unknown> = {},
): string {
  const descriptor = (explanations as Record<string, MessageDescriptor>)[key];
  return descriptor ? fm(descriptor, params as Record<string, string>) : "";
}
