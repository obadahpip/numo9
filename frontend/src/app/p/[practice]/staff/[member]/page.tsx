import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { getFormatMessage } from "@/i18n/server";
import { StaffMemberScreen } from "@/staff/StaffMemberScreen";
import { m } from "@/staff/messages";

interface Params {
  practice: string;
  member: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A practice staff member (V-05-T04, T08), `/p/:practice/staff/:member`. */
export default async function PracticeStaffMemberPage({ params }: { params: Promise<Params> }) {
  const { practice, member } = await params;
  if (!UUID.test(practice) || !UUID.test(member)) notFound();
  const fm = await getFormatMessage();
  return (
    <AppShell practice={practice} section={fm(m.breadcrumb)}>
      <StaffMemberScreen practice={practice} member={member} />
    </AppShell>
  );
}
