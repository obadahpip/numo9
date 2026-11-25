/**
 * Tax settings registry (G-06-T10): every tax setting key, the **one** card of the one page
 * that edits it, and the API write it uses. `registry.test.ts` (run by CI with the unit tests)
 * scans the source and fails when
 *
 * - a key is registered twice or its card isn't an anchor of the page;
 * - a write to a tax-settings endpoint appears outside the registered client modules (a second
 *   page editing a tax setting would need one);
 * - a registered client or the editing screen is used by more than the registered route.
 *
 * To add a tax setting: add its key here, edit it in a card of `TaxSettingsScreen`, nowhere else.
 */
import type { Anchor } from "./api";

export interface TaxSettingEntry {
  /** The card (anchor) of the tax settings page that edits it. */
  anchor: Anchor;
  /** The client module holding the write call. */
  client: string;
  /** The API path (under `/api/v1/o/<org>/`) the write goes to. */
  endpoint: string;
}

/** The page: `/o/:org/settings/registrations` (aliases `settings/tax`, `tax-settings`). */
export const TAX_SETTINGS_ROUTE = "src/app/o/[org]/settings/registrations/page.tsx";

const SETTINGS = { client: "src/tax/settings/api.ts", endpoint: "tax/settings" };
const REGISTRATIONS = {
  anchor: "registrations" as const,
  client: "src/settings/general/registrations.ts",
  endpoint: "tax/registrations",
};

export const TAX_SETTINGS: Record<string, TaxSettingEntry> = {
  "registration.bn": REGISTRATIONS,
  "registration.rt": REGISTRATIONS,
  "registration.rp": REGISTRATIONS,
  "registration.rc": REGISTRATIONS,
  "registration.qst": REGISTRATIONS,
  "registration.pst_bc": REGISTRATIONS,
  "registration.pst_sk": REGISTRATIONS,
  "registration.rst_mb": REGISTRATIONS,
  "tax.basis": { anchor: "tax-basis", ...SETTINGS },
  "tax.default_codes": { anchor: "default-codes", ...SETTINGS },
  "tax.rounding_mode": { anchor: "default-codes", ...SETTINGS },
  "tax.quick_method": { anchor: "quick-method", ...SETTINGS },
  "tax.quick_method_from": { anchor: "quick-method", ...SETTINGS },
  "tax.restricted_itc": {
    anchor: "restricted-itc",
    client: "src/tax/settings/api.ts",
    endpoint: "tax/settings/restricted-itc",
  },
};

/** Endpoints whose writes change a tax setting (matched in source text). */
export const TAX_SETTING_ENDPOINTS = [
  /\/tax\/settings\b/,
  /\/tax\/registrations`?\)?[,;]|taxUrl\(/,
  /\/settings\/registrations\b/,
];

/** Modules that may import a registered client (the screens of the one page). */
export const EDITORS: Record<string, string[]> = {
  "src/tax/settings/api.ts": ["src/tax/settings/TaxSettingsScreen.tsx"],
  "src/settings/general/registrations.ts": ["src/settings/general/RegistrationsScreen.tsx"],
};

/** Screens that edit tax settings and the only modules that may mount them. */
export const MOUNTS: Record<string, string[]> = {
  "src/tax/settings/TaxSettingsScreen.tsx": [TAX_SETTINGS_ROUTE],
  "src/settings/general/RegistrationsScreen.tsx": ["src/tax/settings/TaxSettingsScreen.tsx"],
};

export interface SourceFile {
  /** Path from the frontend root, e.g. `src/tax/settings/api.ts`. */
  path: string;
  text: string;
}

const WRITE = /method:\s*["'`](POST|PATCH|PUT|DELETE)["'`]/;
const isTest = (path: string) => /\.test\.tsx?$|fixtures\.ts$/.test(path);

/** Does `file` import values (not only types) from the module `target`? */
function imports(file: SourceFile, target: string): boolean {
  const wanted = target.replace(/\.tsx?$/, "");
  const statements = file.text.matchAll(/import\s+(type\s+)?[^;]*?from\s+["']([^"']+)["']/g);
  for (const [, typeOnly, spec] of statements) {
    if (typeOnly || !spec) continue;
    let resolved: string;
    if (spec.startsWith("@/")) resolved = `src/${spec.slice(2)}`;
    else if (spec.startsWith(".")) {
      const parts = file.path.split("/").slice(0, -1);
      for (const part of spec.split("/")) {
        if (part === "..") parts.pop();
        else if (part !== ".") parts.push(part);
      }
      resolved = parts.join("/");
    } else continue;
    if (resolved === wanted) return true;
  }
  return false;
}

/** The problems of a source tree against the registry (empty when it holds). */
export function checkTaxSettings(
  files: SourceFile[],
  anchors: readonly string[],
  registry: Record<string, TaxSettingEntry> = TAX_SETTINGS,
): string[] {
  const problems: string[] = [];
  const clients = new Set(Object.values(registry).map((entry) => entry.client));
  for (const [key, entry] of Object.entries(registry)) {
    if (!anchors.includes(entry.anchor)) {
      problems.push(`${key}: "${entry.anchor}" is not a card of the tax settings page`);
    }
    if (!files.some((file) => file.path === entry.client)) {
      problems.push(`${key}: client ${entry.client} does not exist`);
    }
  }
  const source = files.filter((file) => !isTest(file.path));
  for (const file of source) {
    const touches = TAX_SETTING_ENDPOINTS.some((endpoint) => endpoint.test(file.text));
    if (touches && WRITE.test(file.text) && !clients.has(file.path)) {
      problems.push(
        `${file.path}: writes a tax setting outside the registered clients — a tax setting is ` +
          "edited on the one tax settings page only",
      );
    }
    for (const [client, editors] of Object.entries(EDITORS)) {
      if (file.path !== client && imports(file, client) && !editors.includes(file.path)) {
        problems.push(`${file.path}: second editing route — imports ${client}`);
      }
    }
    for (const [screen, mounts] of Object.entries(MOUNTS)) {
      if (file.path !== screen && imports(file, screen) && !mounts.includes(file.path)) {
        problems.push(`${file.path}: second editing route — mounts ${screen}`);
      }
    }
  }
  return problems;
}
