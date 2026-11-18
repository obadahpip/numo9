import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { GroupsScreen } from "@/groups/GroupsScreen";
import { m } from "@/groups/messages";
import { getFormatMessage } from "@/i18n/server";

interface Params {
  practice: string;
}

/** Practice public id (UUID). */
const PRACTICE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function generateMetadata() {
  const fm = await getFormatMessage();
  return { title: `${fm(m.title)} · ${fm(m.breadcrumb)}` };
}

/** Groups and tags of a practice (V-02-T09…T11), `/p/:practice/groups`. */
export default async function PracticeGroupsPage({ params }: { params: Promise<Params> }) {
  const { practice } = await params;
  if (!PRACTICE_ID.test(practice)) notFound();
  const fm = await getFormatMessage();
  return (
    <AppShell practice={practice} section={fm(m.breadcrumb)}>
      <GroupsScreen practice={practice} />
    </AppShell>
  );
}
