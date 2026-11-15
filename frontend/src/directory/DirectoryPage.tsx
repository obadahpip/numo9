"use client";

import { useRouter } from "next/navigation";

import { DirectoryScreen } from "./DirectoryScreen";

/** The directory screen with Next.js navigation (client boundary of the `/p/…` page). */
export function DirectoryPage({ practice }: { practice: string }) {
  const router = useRouter();
  return <DirectoryScreen practice={practice} navigate={(href) => router.push(href)} />;
}
