"use client";

/** The banking page: the home screen and the panels it opens (F-01-T08 …). */
import { BankingHomeScreen } from "./BankingHomeScreen";

export function BankingHome({ org }: { org: string }) {
  return <BankingHomeScreen org={org} />;
}
