// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { ANCHORS } from "./links";
import { checkTaxSettings, TAX_SETTINGS, TAX_SETTINGS_ROUTE, type SourceFile } from "./registry";

/**
 * G-06-T10 — CI check: every tax setting key has exactly one editing route. The real source
 * tree holds; a tree with a duplicate (a second page mounting the screen, another module
 * writing to a tax-settings endpoint, a second user of the client) fails.
 */
const ROOT = join(__dirname, "..", "..", "..");

function walk(dir: string, out: SourceFile[] = []): SourceFile[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, out);
    else if (/\.tsx?$/.test(name)) {
      out.push({
        path: relative(ROOT, path).replaceAll("\\", "/"),
        text: readFileSync(path, "utf8"),
      });
    }
  }
  return out;
}

const FILES = walk(join(ROOT, "src"));

it("the source tree edits every tax setting in exactly one place", () => {
  expect(checkTaxSettings(FILES, ANCHORS)).toEqual([]);
  expect(FILES.some((file) => file.path === TAX_SETTINGS_ROUTE)).toBe(true);
});

it("registers every setting the page edits, each on one card", () => {
  expect(Object.keys(TAX_SETTINGS).sort()).toEqual([
    "registration.bn",
    "registration.pst_bc",
    "registration.pst_sk",
    "registration.qst",
    "registration.rc",
    "registration.rp",
    "registration.rst_mb",
    "registration.rt",
    "tax.basis",
    "tax.default_codes",
    "tax.quick_method",
    "tax.quick_method_from",
    "tax.restricted_itc",
    "tax.rounding_mode",
  ]);
  const screen = FILES.find((f) => f.path === "src/tax/settings/TaxSettingsScreen.tsx")!.text;
  for (const entry of Object.values(TAX_SETTINGS)) {
    expect(screen).toContain(
      entry.anchor === "registrations" ? 'id="registrations"' : `anchor="${entry.anchor}"`,
    );
  }
});

const add = (path: string, text: string) => [...FILES, { path, text }];

it("fails on a second page mounting the editing screen", () => {
  const problems = checkTaxSettings(
    add(
      "src/app/o/[org]/sales/settings/page.tsx",
      'import { TaxSettingsScreen } from "@/tax/settings/TaxSettingsScreen";\nexport default TaxSettingsScreen;',
    ),
    ANCHORS,
  );
  expect(problems).toEqual([
    "src/app/o/[org]/sales/settings/page.tsx: second editing route — mounts src/tax/settings/TaxSettingsScreen.tsx",
  ]);
});

it("fails on another module writing to a tax-settings endpoint or reusing the client", () => {
  const rogue = checkTaxSettings(
    add(
      "src/reports/basis.ts",
      'export const save = (org: string) => apiRequest(`/api/v1/o/${org}/tax/settings`, { method: "PATCH", body: {} });',
    ),
    ANCHORS,
  );
  expect(rogue).toHaveLength(1);
  expect(rogue[0]).toContain("src/reports/basis.ts: writes a tax setting outside");
  const reuse = checkTaxSettings(
    add("src/sales/SalesSettings.tsx", 'import { taxSettingsApi } from "@/tax/settings/api";'),
    ANCHORS,
  );
  expect(reuse).toEqual([
    "src/sales/SalesSettings.tsx: second editing route — imports src/tax/settings/api.ts",
  ]);
  const relativeImport = checkTaxSettings(
    add("src/settings/general/Other.tsx", 'import { addRegistration } from "./registrations";'),
    ANCHORS,
  );
  expect(relativeImport).toHaveLength(1);
});

it("fails on a duplicate or unknown card and a missing client", () => {
  const problems = checkTaxSettings(FILES, ANCHORS, {
    ...TAX_SETTINGS,
    "tax.basis": { anchor: "nowhere" as never, client: "src/tax/settings/api.ts", endpoint: "x" },
    "tax.other": { anchor: "tax-basis", client: "src/missing.ts", endpoint: "x" },
  });
  expect(problems).toEqual([
    'tax.basis: "nowhere" is not a card of the tax settings page',
    "tax.other: client src/missing.ts does not exist",
  ]);
});
