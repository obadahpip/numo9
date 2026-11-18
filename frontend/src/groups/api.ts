/**
 * Client for the practice groups and tags API (V-02-T07, docs/architecture/directory.md):
 * `/api/v1/practice/groups…` and `/api/v1/practice/tags…`. Every call resolves (never throws on
 * an HTTP error): screens branch on `status`.
 */
import { apiRequest } from "@/auth/client";

export const GROUPS_URL = "/api/v1/practice/groups";
export const TAGS_URL = "/api/v1/practice/tags";

export interface Group {
  id: string;
  name: string;
  parent: string | null;
  depth: number;
  has_children: boolean;
  organisation_count: number;
  subtree_organisation_count: number;
  staff_count: number;
}

export interface GroupImpact {
  groups: number;
  organisations: number;
  staff_assignments: number;
  staff: number;
  staff_losing_access: number;
}

export type TagColour =
  | "red"
  | "orange"
  | "amber"
  | "olive"
  | "green"
  | "teal"
  | "cyan"
  | "blue"
  | "indigo"
  | "violet"
  | "magenta"
  | "slate";

export const TAG_COLOURS: TagColour[] = [
  "red",
  "orange",
  "amber",
  "olive",
  "green",
  "teal",
  "cyan",
  "blue",
  "indigo",
  "violet",
  "magenta",
  "slate",
];

export interface Tag {
  id: string;
  name: string;
  colour: TagColour;
  colour_label: string;
  organisation_count: number;
}

/** A refusal's message (400/403 `{"detail"}`), or null. */
export function refusal(result: { status: number; body: unknown }): string | null {
  const detail = (result.body as { detail?: unknown } | null)?.detail;
  return result.status >= 400 && typeof detail === "string" ? detail : null;
}

const q = (practice: string) => `?practice=${encodeURIComponent(practice)}`;

export const groupsApi = {
  list: (practice: string) =>
    apiRequest<{ practice: string; groups: Group[] }>(`${GROUPS_URL}${q(practice)}`),
  create: (practice: string, name: string, parent: string | null) =>
    apiRequest<Group>(GROUPS_URL, { method: "POST", body: { practice, name, parent } }),
  rename: (id: string, name: string) =>
    apiRequest<Group>(`${GROUPS_URL}/${id}`, { method: "PATCH", body: { name } }),
  move: (id: string, parent: string | null) =>
    apiRequest<Group>(`${GROUPS_URL}/${id}`, { method: "PATCH", body: { parent } }),
  impact: (id: string) => apiRequest<GroupImpact>(`${GROUPS_URL}/${id}/impact`),
  remove: (id: string) => apiRequest<unknown>(`${GROUPS_URL}/${id}`, { method: "DELETE" }),
  tags: (practice: string) =>
    apiRequest<{ practice: string; tags: Tag[] }>(`${TAGS_URL}${q(practice)}`),
  createTag: (practice: string, name: string, colour: TagColour) =>
    apiRequest<Tag>(TAGS_URL, { method: "POST", body: { practice, name, colour } }),
  tagOrganisations: (tag: string, organisations: string[]) =>
    apiRequest<{ count: number }>(`${TAGS_URL}/${tag}/organisations`, {
      method: "POST",
      body: { organisations },
    }),
  untagOrganisation: (tag: string, organisation: string) =>
    apiRequest<unknown>(`${TAGS_URL}/${tag}/organisations/${organisation}`, { method: "DELETE" }),
};

export const MAX_DEPTH = 5;

/** Groups a group may move under: not itself or a descendant, and the subtree stays ≤ 5 deep.
 * `null` (top level) is always offered unless the group is already there. */
export function moveTargets(groups: Group[], moving: Group): (Group | null)[] {
  const byId = new Map(groups.map((g) => [g.id, g]));
  const inside = new Set<string>([moving.id]);
  for (const group of groups) {
    let cursor: Group | undefined = group;
    while (cursor?.parent) {
      if (inside.has(cursor.parent) || cursor.parent === moving.id) {
        inside.add(group.id);
        break;
      }
      cursor = byId.get(cursor.parent);
    }
  }
  const height =
    Math.max(...groups.filter((g) => inside.has(g.id)).map((g) => g.depth)) - moving.depth + 1;
  const targets: (Group | null)[] = moving.parent ? [null] : [];
  for (const group of groups) {
    if (inside.has(group.id) || group.id === moving.parent) continue;
    if (group.depth + height <= MAX_DEPTH) targets.push(group);
  }
  return targets;
}
