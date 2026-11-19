import type { MessageDescriptor } from "@/i18n";

import type { ContactRoleKey } from "./api";
import { lm } from "./listMessages";

export const ROLES: ContactRoleKey[] = [
  "customer",
  "supplier",
  "contractor",
  "government_agency",
  "employee",
];

export const ROLE_LABEL: Record<ContactRoleKey, MessageDescriptor> = {
  customer: lm.roleCustomer,
  supplier: lm.roleSupplier,
  contractor: lm.roleContractor,
  government_agency: lm.roleAgency,
  employee: lm.roleEmployee,
};

/** The list's title per tab (gap-19): each role's list says what it lists. */
export const ROLE_TITLE: Record<ContactRoleKey, MessageDescriptor> = {
  customer: lm.titleCustomer,
  supplier: lm.titleSupplier,
  contractor: lm.titleContractor,
  government_agency: lm.titleAgency,
  employee: lm.titleEmployee,
};
