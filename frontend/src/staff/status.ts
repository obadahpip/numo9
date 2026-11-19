/**
 * One staff status shown on the list and on a person's page (V-05-T09). People statuses are not
 * document statuses, so they use the Badge tones directly (not the documents' STATUS_TONES map).
 */
import type { BadgeTone } from "@numo9/ui";

import type { FormatMessage } from "@/i18n";

import type { StaffMember } from "./api";
import { m } from "./messages";

export type StaffStatus = "active" | "dormant" | "suspended" | "pending";

/** Dormant only applies to active members (suspended and pending people can't sign in). */
export function staffStatus(person: Pick<StaffMember, "status" | "dormant">): StaffStatus {
  if (person.status === "active" && person.dormant) return "dormant";
  return person.status;
}

export function staffStatusLabel(status: StaffStatus, fm: FormatMessage): string {
  switch (status) {
    case "active":
      return fm(m.statusActive);
    case "dormant":
      return fm(m.statusDormant);
    case "suspended":
      return fm(m.statusSuspended);
    case "pending":
      return fm(m.statusPending);
  }
}

export const STAFF_STATUS_TONES: Record<StaffStatus, BadgeTone> = {
  active: "success",
  dormant: "warning",
  suspended: "danger",
  pending: "info",
};
