import type { OrgSwitcherLabels, SwitcherOrg } from "./OrgSwitcher";

/** Sample org switcher data (Canadian sample organisations) shared by the stories and the tests. */
export const switcherLabels: OrgSwitcherLabels = {
  button: "Switch organisation",
  panel: "Organisations",
  search: "Search organisations",
  recent: "Recent",
  results: "Results",
  noResults: "No organisations match. Try another spelling, or open the directory.",
  loading: "Loading organisations…",
  error: "Organisations couldn't be loaded.",
  retry: "Try again",
  openDirectory: "Open directory",
  current: "Current",
  moreResults: (shown, total) =>
    `Showing ${shown} of ${total}. Refine your search or open the directory.`,
};

export const sampleOrganisations: SwitcherOrg[] = [
  { id: "org-maple", name: "Maple Leaf Supply Ltd.", badge: "via Profitex" },
  { id: "org-north", name: "Northern Lights Bakery Inc.", badge: "via Profitex" },
  { id: "org-erable", name: "Érable Québec Rénovations", badge: "via Profitex" },
  { id: "org-bay", name: "Bay Street Dental Professional Corp.", badge: "via Profitex" },
  { id: "org-prairie", name: "Prairie Wheat Co-op" },
  { id: "org-rocky", name: "Rocky Mountain Outfitters Ltd.", badge: "via Profitex" },
  { id: "org-harbour", name: "Halifax Harbour Charters", badge: "via Profitex" },
];

/** 2,000 generated organisations: the practice-size case the switcher must stay fast for. */
export function manyOrganisations(count = 2000): SwitcherOrg[] {
  const words = ["Maple", "Cedar", "Harbour", "Prairie", "Northern", "Granite", "Coastal", "Birch"];
  const kinds = ["Bakery", "Dental", "Logistics", "Renovations", "Farms", "Studio", "Consulting"];
  return Array.from({ length: count }, (_, index) => ({
    id: `org-${index}`,
    name: `${words[index % words.length]} ${kinds[index % kinds.length]} ${index + 1} Ltd.`,
    badge: "via Profitex",
  }));
}
