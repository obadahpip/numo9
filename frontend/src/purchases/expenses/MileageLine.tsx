"use client";

/**
 * A trip on the expense claim form (E-04-T09): date, from, to and the kilometres driven. The
 * server prices it at the CRA rate when the claim is saved.
 */
import { Button, Input } from "@numo9/ui";
import { useId } from "react";

import { useFormatMessage } from "@/i18n";

import { Labelled, type FormLine } from "./fields";
import { fm as fmm } from "./formMessages";

export interface MileageLineProps {
  org: string;
  claimId?: string;
  line: FormLine;
  index: number;
  lines: FormLine[];
  onChange: (patch: Partial<FormLine>) => void;
  onRemove: () => void;
}

export function MileageLine({ line, index, onChange, onRemove }: MileageLineProps) {
  const fm = useFormatMessage();
  const ids = useId();
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-sm font-semibold text-fg">
        {fm(fmm.tripLegend, { n: index + 1 })}
      </legend>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <Labelled id={`${ids}-date`} label={fm(fmm.date)}>
          <Input
            id={`${ids}-date`}
            type="date"
            value={line.date}
            onChange={(e) => onChange({ date: e.target.value })}
          />
        </Labelled>
        <Labelled id={`${ids}-from`} label={fm(fmm.from)}>
          <Input
            id={`${ids}-from`}
            value={line.fromPlace}
            onChange={(e) => onChange({ fromPlace: e.target.value })}
          />
        </Labelled>
        <Labelled id={`${ids}-to`} label={fm(fmm.to)}>
          <Input
            id={`${ids}-to`}
            value={line.toPlace}
            onChange={(e) => onChange({ toPlace: e.target.value })}
          />
        </Labelled>
        <Labelled id={`${ids}-km`} label={fm(fmm.km)}>
          <Input
            id={`${ids}-km`}
            inputMode="decimal"
            numeric
            value={line.km}
            onChange={(e) => onChange({ km: e.target.value.replace(/[^0-9.]/g, "") })}
          />
        </Labelled>
      </div>
      <div>
        <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
          {fm(fmm.remove)}
        </Button>
      </div>
    </fieldset>
  );
}
