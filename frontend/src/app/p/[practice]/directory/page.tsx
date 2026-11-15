import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { DirectoryPage } from "@/directory/DirectoryPage";
import { m } from "@/directory/messages";
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

/** Organisation directory of a practice (V-01), `/p/:practice/directory`. */
export default async function PracticeDirectoryPage({ params }: { params: Promise<Params> }) {
  const { practice } = await params;
  if (!PRACTICE_ID.test(practice)) notFound();
  const fm = await getFormatMessage();
  return (
    <AppShell practice={practice} section={fm(m.breadcrumb)}>
      <DirectoryPage practice={practice} />
    </AppShell>
  );
}
