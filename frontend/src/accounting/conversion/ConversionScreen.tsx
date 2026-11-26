"use client";

/** The conversion balances screen (C-05): the wizard with its difference meter and its open
 * invoices / bills grids. */
import { ConversionWizard } from "./ConversionWizard";
import { DifferenceMeter } from "./DifferenceMeter";
import { DocumentsGrid } from "./DocumentsGrid";

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
      renderDocuments={({ kind, documents, readOnly, onChanged }) => (
        <DocumentsGrid
          key={kind}
          org={org}
          kind={kind}
          documents={documents}
          readOnly={readOnly}
          onChanged={onChanged}
        />
      )}
    />
  );
}
