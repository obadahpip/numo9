import type { ReactNode } from "react";

import { SettingsNav } from "./SettingsNav";

interface SettingsLayoutProps {
  org: string;
  /** The section shown, e.g. `settings/general`. */
  section: string;
  children: ReactNode;
}

/**
 * Two-column frame of every settings page (A-05-T10): the settings navigation on the left
 * (above the content below 768 px) and the section's own screen on the right.
 */
export function SettingsLayout({ org, section, children }: Readonly<SettingsLayoutProps>) {
  return (
    <div className="flex flex-col gap-6 md:grid md:grid-cols-[13rem_minmax(0,1fr)] md:items-start">
      <SettingsNav org={org} current={section} />
      <div data-settings-section={section} className="min-w-0">
        {children}
      </div>
    </div>
  );
}
