import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { UsersRolesScreen } from "@/settings/users-roles/UsersRolesScreen";

interface Params {
  org: string;
}

/**
 * Settings → Users and roles (A-03-T11…T13), `/o/:org/settings/users-roles`. Replaces the
 * route-registry placeholder; `?tab=roles` / `?tab=limits` open the other tabs.
 */
export default async function UsersRolesPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const [{ org }, { tab }] = await Promise.all([params, searchParams]);
  if (!ORG_SLUG.test(org)) notFound();
  const initial = tab === "roles" || tab === "limits" ? tab : "users";
  return (
    <AppShell org={org} modulePath="settings/users-roles">
      <UsersRolesScreen org={org} tab={initial} />
    </AppShell>
  );
}
