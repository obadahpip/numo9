/** Accounts of the API as the design system's pickers take them (D-01 grid, journals, banking). */
import type { PickerAccount } from "@numo9/ui";

import type { Account } from "./api";

export function pickerAccount(a: Account): PickerAccount {
  return {
    id: a.id,
    code: a.code,
    name: a.name,
    type: a.type,
    subtype: a.subtype as PickerAccount["subtype"],
    detail: a.subtype_label,
    systemRole: a.system_role || undefined,
    isBank: a.is_bank,
    depth: a.depth,
    postable: !a.has_children,
  };
}
