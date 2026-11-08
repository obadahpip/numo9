import { notFound, permanentRedirect } from "next/navigation";

import { ORG_SLUG, orgModuleUrl } from "@/routing/routes";

/** `/o/:org` → organisation Home. The middleware normally answers first; this is the fallback. */
export default async function OrganisationRoot({ params }: { params: Promise<{ org: string }> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  permanentRedirect(orgModuleUrl(org, "home"));
}
