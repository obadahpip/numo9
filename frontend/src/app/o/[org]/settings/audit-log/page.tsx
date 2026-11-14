import { notFound } from "next/navigation";

import { AuditLogScreen } from "@/audit/AuditLogScreen";
import type { AuditFilters } from "@/audit/api";
import { AppShell } from "@/components/AppShell";
import { SettingsLayout } from "@/settings/SettingsLayout";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

type Search = Record<string, string | string[] | undefined>;

const one = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

/** Filters given in the URL (links to one bulk operation or one record's history). */
function filtersFrom(search: Search): AuditFilters {
  const filters: AuditFilters = {};
  for (const key of [
    "from",
    "to",
    "user",
    "action",
    "q",
    "batch",
    "object_type",
    "object_id",
  ] as const) {
    const value = one(search[key]);
    if (value) filters[key] = value;
  }
  const types = search.type;
  if (types) filters.type = Array.isArray(types) ? types : [types];
  return filters;
}

/**
 * Settings → Audit log (A-04-T09), `/o/:org/settings/audit-log`. Replaces the route-registry
 * placeholder.
 */
export default async function AuditLogPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<Search>;
}) {
  const [{ org }, search] = await Promise.all([params, searchParams]);
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/audit-log">
      <SettingsLayout org={org} section="settings/audit-log">
        <AuditLogScreen org={org} initial={filtersFrom(search)} />
      </SettingsLayout>
    </AppShell>
  );
}
