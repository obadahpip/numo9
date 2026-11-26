"use client";

/** The purchase order page (E-01-T11): the editor, navigating to the saved PO. */
import { useRouter } from "next/navigation";

import { PurchaseOrderEditor } from "./PurchaseOrderEditor";

export function PurchaseOrderScreen({ org, id }: { org: string; id?: string }) {
  const router = useRouter();
  return <PurchaseOrderEditor org={org} id={id} navigate={(href) => router.replace(href)} />;
}
