"use client";

/** The purchase order list page (E-01-T13). */
import { useRouter } from "next/navigation";

import { PurchaseOrderList } from "./PurchaseOrderList";

export function PurchaseOrderListScreen({ org }: { org: string }) {
  const router = useRouter();
  return <PurchaseOrderList org={org} navigate={(href) => router.push(href)} />;
}
