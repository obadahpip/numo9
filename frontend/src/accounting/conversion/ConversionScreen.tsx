"use client";

/** The conversion balances screen (C-05): the wizard with its difference meter. */
import { ConversionWizard } from "./ConversionWizard";
import { DifferenceMeter } from "./DifferenceMeter";

export function ConversionScreen({ org }: { org: string }) {
  return (
    <ConversionWizard
      org={org}
      renderMeter={({ overview, rows, readOnly, lockBalances, onFinalised }) => (
        <DifferenceMeter
          org={org}
          rows={rows}
          server={overview.difference}
          conversionDate={overview.session?.conversion_date ?? ""}
          finalised={readOnly}
          lockBalances={lockBalances}
          onFinalised={onFinalised}
        />
      )}
    />
  );
}
