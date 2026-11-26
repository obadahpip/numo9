"use client";

/** Mark as filed and amend (G-03-T12). */
import type { TaxReturn } from "./api";

export interface ReturnActionsProps {
  org: string;
  data: TaxReturn;
  onChange: (next: TaxReturn) => void;
}

export function ReturnActions(_props: ReturnActionsProps) {
  return null;
}
