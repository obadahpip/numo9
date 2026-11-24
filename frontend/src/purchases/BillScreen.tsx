"use client";

/** The bill page (E-02-T11…T14): the split-view editor with its side panels. */
import { useRouter } from "next/navigation";

import { BillEditor } from "./BillEditor";

export function BillScreen({
  org,
  id,
  documentId,
}: {
  org: string;
  id?: string;
  documentId?: string | null;
}) {
  const router = useRouter();
  return (
    <BillEditor
      org={org}
      id={id}
      documentId={documentId}
      navigate={(href) => router.replace(href)}
    />
  );
}
