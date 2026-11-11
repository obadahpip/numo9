import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { RoleEditor } from "@/settings/users-roles/RoleEditor";

const ROLE = /^(new|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;

/**
 * Role editor (A-03-T12): `/o/:org/settings/users-roles/roles/new[?copy=<role>]` creates a custom
 * role; `/roles/<id>` edits a custom role or shows a system role read-only.
 */
export default async function RoleEditorPage({
  params,
  searchParams,
}: {
  params: Promise<{ org: string; role: string }>;
  searchParams: Promise<{ copy?: string }>;
}) {
  const [{ org, role }, { copy }] = await Promise.all([params, searchParams]);
  if (!ORG_SLUG.test(org) || !ROLE.test(role)) notFound();
  return (
    <AppShell org={org} modulePath="settings/users-roles">
      <RoleEditor org={org} roleId={role} copyFrom={copy} />
    </AppShell>
  );
}
