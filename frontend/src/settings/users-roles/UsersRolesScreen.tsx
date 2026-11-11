"use client";

import {
  ExplainPanel,
  LoadingRegion,
  SkeletonTable,
  Tabs,
  ToastProvider,
  type TabItem,
} from "@numo9/ui";
import { useCallback, useEffect, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { isOk, orgApi, usersRolesApi, type ApiError, type Role } from "./api";
import { apiRequest } from "@/auth/client";
import { LimitsPanel } from "./LimitsPanel";
import { PermissionExplain } from "@/components/PermissionExplain";

import { MembersPanel } from "./MembersPanel";
import { m, rm } from "./messages";
import { RolesPanel } from "./RolesPanel";

const toastLabels = defineMessages({
  region: {
    id: "settings.usersRoles.toastRegion",
    defaultMessage: "Notifications ({hotkey})",
    description: "Name of the toast region; {hotkey} is the keyboard shortcut",
  },
});

export type UsersRolesTab = "users" | "roles" | "limits";

interface Access {
  permissions: Set<string>;
  roles: Role[];
}

type State =
  | { kind: "loading" }
  | { kind: "ready"; access: Access }
  | { kind: "denied"; error: ApiError }
  | { kind: "notFound" }
  | { kind: "failed" };

/**
 * Settings → Users and roles (A-03-T11…T13): tabs for the people and their roles, the roles
 * themselves and approval limits. Each tab shows only what the user's permissions allow (from
 * `GET …/my-permissions`); the API enforces it either way.
 */
export function UsersRolesScreen({
  org,
  tab = "users",
  saved,
  deleted,
}: {
  org: string;
  tab?: UsersRolesTab;
  /** Name of the role the editor just saved / deleted (status line on the Roles tab). */
  saved?: string;
  deleted?: string;
}) {
  const fm = useFormatMessage();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [current, setCurrent] = useState<UsersRolesTab>(tab);

  const load = useCallback(async () => {
    const mine = await apiRequest<{ permissions: string[] } | ApiError>(
      orgApi(org, "my-permissions"),
    );
    if (mine.status === 404) return setState({ kind: "notFound" });
    if (!isOk<{ permissions: string[] }>(mine)) return setState({ kind: "failed" });
    const permissions = new Set(mine.body.permissions);
    if (!permissions.has("organisation.members.view") && !permissions.has("roles.role.view")) {
      // Ask for the list anyway: the refusal carries the "why can't I?" payload (A-03-T14).
      const refused = await usersRolesApi.members(org);
      return setState({ kind: "denied", error: refused.body as ApiError });
    }
    let roles: Role[] = [];
    if (
      permissions.has("roles.role.view") ||
      permissions.has("roles.assignment.manage") ||
      permissions.has("roles.limit.view")
    ) {
      const listed = await usersRolesApi.roles(org);
      if (isOk<Role[]>(listed)) roles = listed.body;
    }
    setState({ kind: "ready", access: { permissions, roles } });
  }, [org]);

  useEffect(() => {
    void load();
  }, [load]);

  let body;
  if (state.kind === "loading") {
    body = (
      <LoadingRegion label={fm(m.loading)}>
        <SkeletonTable rows={5} columns={4} />
      </LoadingRegion>
    );
  } else if (state.kind === "notFound") {
    body = <ExplainPanel kind="notFound" title={fm(m.notFoundTitle)} body={fm(m.notFoundBody)} />;
  } else if (state.kind === "denied") {
    body = <PermissionExplain org={org} error={state.error} />;
  } else if (state.kind === "failed") {
    body = <ExplainPanel kind="notFound" title={fm(m.loadFailed)} body={fm(m.failed)} />;
  } else {
    const { permissions, roles } = state.access;
    const items: TabItem[] = [];
    if (permissions.has("organisation.members.view")) {
      items.push({
        value: "users",
        label: fm(m.tabUsers),
        content: (
          <MembersPanel
            org={org}
            roles={roles}
            canAssign={permissions.has("roles.assignment.manage")}
            onChanged={() => void load()}
          />
        ),
      });
    }
    if (permissions.has("roles.role.view")) {
      const notice = saved
        ? fm(rm.saved, { role: saved })
        : deleted
          ? fm(rm.deleted, { role: deleted })
          : undefined;
      items.push({
        value: "roles",
        label: fm(m.tabRoles),
        content: (
          <RolesPanel
            org={org}
            roles={roles}
            canManage={permissions.has("roles.role.manage")}
            notice={notice}
          />
        ),
      });
    }
    if (permissions.has("roles.limit.view")) {
      items.push({
        value: "limits",
        label: fm(m.tabLimits),
        content: (
          <LimitsPanel org={org} roles={roles} canManage={permissions.has("roles.limit.manage")} />
        ),
      });
    }
    body = (
      <Tabs
        label={fm(m.tabs)}
        items={items}
        value={items.some((i) => i.value === current) ? current : items[0]?.value}
        onValueChange={(value) => setCurrent(value as UsersRolesTab)}
      />
    );
  }

  return (
    <ToastProvider
      labels={{ region: fm(toastLabels.region, { hotkey: "F8" }), close: fm(m.close) }}
    >
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
          <p className="mt-1 text-sm text-fg-muted">{fm(m.intro)}</p>
        </div>
        {body}
      </div>
    </ToastProvider>
  );
}
