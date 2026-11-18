import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { getFormatMessage } from "@/i18n/server";
import { m } from "@/staff/messages";
import { StaffListScreen } from "@/staff/StaffListScreen";

interface Params {
  practice: string;
}

/** Practice public id (UUID). */
const PRACTICE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function generateMetadata() {
  const fm = await getFormatMessage();
  return { title: fm(m.listTitle) };
}

/** The practice's staff (V-05-T09), `/p/:practice/staff`. */
export default async function PracticeStaffPage({ params }: { params: Promise<Params> }) {
  const { practice } = await params;
  if (!PRACTICE_ID.test(practice)) notFound();
  const fm = await getFormatMessage();
  return (
    <AppShell practice={practice} section={fm(m.breadcrumb)}>
      <StaffListScreen practice={practice} />
    </AppShell>
  );
}
