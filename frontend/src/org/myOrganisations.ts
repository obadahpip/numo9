/**
 * Organisations the signed-in user can access (A-01-T14), from `GET /api/v1/me/organisations`
 * (A-01-T13). The response is cached for the page session so moving between modules doesn't
 * refetch it; a failed request is not cached, so "Try again" asks the server again.
 */
export const MY_ORGANISATIONS_URL = "/api/v1/me/organisations";

/** One entry of `GET /api/v1/me/organisations` (MyOrganisationSerializer). */
export interface MyOrganisation {
  id: string;
  name: string;
  status: string;
  time_zone: string;
  /** Default language of the organisation's documents (A-10-T14): "en-ca" | "fr-ca". */
  locale?: string;
  membership: { role: string } | null;
  via_practices: {
    practice_id: string;
    practice_name: string;
    practice_role: string;
    assignment_role: string;
    assigned_staff: boolean;
  }[];
}

let cache: Promise<MyOrganisation[]> | undefined;

export function loadMyOrganisations(fetcher: typeof fetch = fetch): Promise<MyOrganisation[]> {
  cache ??= fetcher(MY_ORGANISATIONS_URL, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`${MY_ORGANISATIONS_URL} answered ${response.status}`);
      const body: unknown = await response.json();
      if (!Array.isArray(body)) throw new Error(`${MY_ORGANISATIONS_URL}: expected a list`);
      return body as MyOrganisation[];
    })
    .catch((error: unknown) => {
      cache = undefined;
      throw error;
    });
  return cache;
}

/** Forget the cached list (tests; after creating or leaving an organisation). */
export function resetMyOrganisations(): void {
  cache = undefined;
}

/**
 * The practice the user acts through for an organisation: none when the user is a direct member
 * (they act as themselves), otherwise the first practice giving access (alphabetical, as the API
 * orders them).
 */
export function actingPractice(
  org: MyOrganisation,
): MyOrganisation["via_practices"][number] | null {
  if (org.membership) return null;
  return org.via_practices[0] ?? null;
}

/** The practice whose directory "Open directory" opens: the first practice found, if any. */
export function directoryPractice(orgs: readonly MyOrganisation[]): string | undefined {
  for (const org of orgs) {
    const practice = org.via_practices[0];
    if (practice) return practice.practice_id;
  }
  return undefined;
}
