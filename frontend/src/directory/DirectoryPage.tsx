"use client";

import { useRouter } from "next/navigation";

import { DormantStaffWidget } from "@/staff/DormantStaffWidget";

import { DirectoryScreen } from "./DirectoryScreen";

/** The directory screen with Next.js navigation (client boundary of the `/p/…` page). */
export function DirectoryPage({ practice }: { practice: string }) {
  const router = useRouter();
  return (
    <div className="flex flex-col gap-4">
      {/* V-05-T06: the practice home's dormant-staff widget (admins only; empty → nothing). */}
      <DormantStaffWidget practice={practice} />
      <DirectoryScreen practice={practice} navigate={(href) => router.push(href)} />
    </div>
  );
}
