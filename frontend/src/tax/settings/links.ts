/**
 * Deep links to the one tax settings page (G-06-T09): every "tax settings" link elsewhere in
 * the app is built here and lands on the card (anchor) that edits the setting. This module has
 * no API client: any screen may import it (the registry check, G-06-T10, allows it).
 */

/** Anchors of the page: deep links from other modules land on them. */
export const ANCHORS = [
  "registrations",
  "tax-basis",
  "default-codes",
  "quick-method",
  "restricted-itc",
] as const;
export type Anchor = (typeof ANCHORS)[number];

export const taxSettingsUrl = (org: string, anchor?: Anchor) =>
  `/o/${org}/settings/registrations${anchor ? `#${anchor}` : ""}`;
