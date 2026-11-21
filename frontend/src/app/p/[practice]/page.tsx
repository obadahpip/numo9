import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { m } from "@/dashboard/messages";
import { PracticeHomeScreen } from "@/dashboard/PracticeHomeScreen";
import { getFormatMessage } from "@/i18n/server";

interface Params {
  practice: string;
}

/** Practice public id (UUID). */
const PRACTICE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function generateMetadata() {
  const fm = await getFormatMessage();
  return { title: `${fm(m.title)} · Numo9` };
}

/** Practice home (V-04), `/p/:practice`: the cross-organisation dashboard. */
export default async function PracticeHomePage({ params }: { params: Promise<Params> }) {
  const { practice } = await params;
  if (!PRACTICE_ID.test(practice)) notFound();
  const fm = await getFormatMessage();
  return (
    <AppShell practice={practice} section={fm(m.crumb)}>
      <PracticeHomeScreen practice={practice} />
    </AppShell>
  );
}
