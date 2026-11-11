"use client";

import { Badge, Button } from "@numo9/ui";
import Link from "next/link";

import { useFormatMessage } from "@/i18n";

import type { Role } from "./api";
import { rm } from "./messages";

export const rolesTabUrl = (org: string) => `/o/${org}/settings/users-roles?tab=roles`;
export const roleUrl = (org: string, role: string) =>
  `/o/${org}/settings/users-roles/roles/${role}`;

/**
 * Roles tab (A-03-T12): system roles (read-only, can be copied) then the organisation's custom
 * roles, each with how many people hold it; "New role" opens the role editor.
 */
export function RolesPanel({
  org,
  roles,
  canManage,
  notice,
}: {
  org: string;
  roles: Role[];
  canManage: boolean;
  notice?: string;
}) {
  const fm = useFormatMessage();
  const shown = roles.filter((r) => r.scope === "organisation");
  return (
    <div className="flex flex-col gap-4">
      {notice ? (
        <p
          role="status"
          className="rounded-md border-2 border-border bg-surface-success-subtle px-4 py-3 text-sm"
        >
          {notice}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{fm(rm.heading)}</h2>
        {canManage ? (
          <Button asChild>
            <Link href={roleUrl(org, "new")}>{fm(rm.newRole)}</Link>
          </Button>
        ) : null}
      </div>
      <ul
        aria-label={fm(rm.listLabel)}
        className="divide-y divide-border rounded-lg border border-border"
      >
        {shown.map((role) => (
          <li key={role.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href={roleUrl(org, role.id)}
                  aria-label={fm(rm.open, { role: role.name })}
                  className="font-semibold text-fg underline-offset-2 hover:underline"
                >
                  {role.name}
                </Link>
                <Badge tone={role.is_system ? "neutral" : "accent"}>
                  {fm(role.is_system ? rm.system : rm.custom)}
                </Badge>
              </div>
              {role.description ? (
                <p className="mt-1 text-sm text-fg-muted">{role.description}</p>
              ) : null}
              <p className="mt-1 text-xs text-fg-muted">
                {fm(rm.stats, {
                  holders: fm(rm.holders, { count: role.holders }),
                  permissions: fm(rm.permissionCount, { count: role.permissions.length }),
                })}
              </p>
            </div>
            {canManage ? (
              <Link
                href={`${roleUrl(org, "new")}?copy=${role.id}`}
                className="text-sm font-semibold text-fg underline underline-offset-2"
              >
                {fm(rm.copyRole, { role: role.name })}
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
