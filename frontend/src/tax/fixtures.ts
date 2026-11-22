/** Tax codes as the API returns them (G-01-T11), for component tests and stories. */
import type { TaxCode } from "./api";

export const ORG = "refined";

export function taxCode(over: Partial<TaxCode> = {}): TaxCode {
  return {
    id: "c-on",
    code: "sales.ON.standard",
    version: 1,
    name: "HST 13 % (Ontario) on sales",
    name_i18n: { "en-ca": "HST 13 % (Ontario) on sales" },
    side: "sales",
    type: "taxable",
    type_label: "Taxable",
    province: "ON",
    effective_from: "2010-07-01",
    effective_to: null,
    expired: false,
    archived_at: null,
    itc_restriction_pct: null,
    rate: "13",
    components: [
      { id: "k1", key: "hst_on", name: "HST (ON)", kind: "hst", rate: "13", recoverable_pct: null },
    ],
    usage_count: 412,
    ...over,
  };
}

export const CODES: TaxCode[] = [
  taxCode(),
  taxCode({
    id: "c-bc",
    code: "sales.BC.standard",
    name: "GST 5 % + PST 7 % (British Columbia) on sales",
    province: "BC",
    rate: "12",
    components: [
      { id: "k2", key: "gst", name: "GST", kind: "gst", rate: "5", recoverable_pct: null },
      { id: "k3", key: "pst_bc", name: "PST (BC)", kind: "pst", rate: "7", recoverable_pct: null },
    ],
    usage_count: 0,
  }),
  taxCode({
    id: "c-zero",
    code: "sales.zero_rated",
    name: "Zero-rated on sales (0 %)",
    type: "zero_rated",
    type_label: "Zero-rated",
    province: "",
    rate: "0",
    components: [
      {
        id: "k4",
        key: "gst_zero",
        name: "GST/HST zero-rated",
        kind: "gst",
        rate: "0",
        recoverable_pct: null,
      },
    ],
    usage_count: 9,
  }),
  taxCode({
    id: "c-exempt",
    code: "sales.exempt",
    name: "Exempt on sales",
    type: "exempt",
    type_label: "Exempt",
    province: "",
    rate: "0",
    components: [],
    usage_count: 1,
  }),
  taxCode({
    id: "p-on",
    code: "purchase.ON.standard.itc50",
    name: "HST 13 % (Ontario) on purchases, 50 % ITC",
    side: "purchase",
    itc_restriction_pct: "50",
    usage_count: 3,
  }),
];

export const EXPIRED_MB = taxCode({
  id: "c-mb1",
  code: "sales.MB.standard",
  version: 1,
  name: "GST 5 % + RST 8 % (Manitoba) on sales",
  province: "MB",
  effective_from: "2013-07-01",
  effective_to: "2019-06-30",
  expired: true,
  rate: "13",
  components: [
    { id: "k2", key: "gst", name: "GST", kind: "gst", rate: "5", recoverable_pct: null },
    { id: "k5", key: "rst_mb", name: "RST (MB)", kind: "pst", rate: "8", recoverable_pct: null },
  ],
  usage_count: 0,
});
