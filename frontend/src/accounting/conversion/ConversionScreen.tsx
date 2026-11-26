"use client";

/** The conversion balances screen (C-05): the wizard with its parts. */
import { ConversionWizard } from "./ConversionWizard";

export function ConversionScreen({ org }: { org: string }) {
  return <ConversionWizard org={org} />;
}
