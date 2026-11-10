import { z } from "zod";

import type { FormLabels } from "./Form";

/** Sample form-kit labels and a Settings → General schema (stories and tests). */
export const formLabels: FormLabels = {
  errorSummaryTitle: (count) =>
    count === 1
      ? "There is 1 problem with this form"
      : `There are ${count} problems with this form`,
  save: "Save settings",
  saving: "Saving…",
  discard: "Discard changes",
  unsavedChanges: "You have unsaved changes.",
  leaveTitle: "Leave without saving?",
  leaveBody: "Your changes to these settings will be lost.",
  stay: "Stay on this page",
  leave: "Leave without saving",
  close: "Close",
};

export const generalSettingsSchema = z.object({
  legalName: z
    .string()
    .trim()
    .min(1, "Enter the legal name — it prints on every statement.")
    .refine((value) => !/^\d+$/.test(value), {
      message:
        "Legal name can't be only numbers — it prints on every statement. Enter the registered business name, e.g. 'Refined Interiors Inc.'",
    }),
  province: z.string().min(1, "Choose the Province where the business is registered."),
  postalCode: z
    .string()
    .trim()
    .regex(/^[A-Za-z]\d[A-Za-z] ?\d[A-Za-z]\d$/, "Postal code should look like 'M5V 2T6'."),
  newsletter: z.boolean(),
});

export type GeneralSettings = z.infer<typeof generalSettingsSchema>;

export const generalDefaults: GeneralSettings = {
  legalName: "Maple Leaf Supply Ltd.",
  province: "ON",
  postalCode: "M5V 2T6",
  newsletter: false,
};

export const provinceOptions = [
  { value: "AB", label: "Alberta" },
  { value: "BC", label: "British Columbia" },
  { value: "ON", label: "Ontario" },
  { value: "QC", label: "Quebec" },
];
