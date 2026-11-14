// @vitest-environment node
import { fileURLToPath } from "node:url";

import { ESLint } from "eslint";

import { ORG_MODULES } from "@/routing/routes";
import { CORE, isFeatureKey } from "@/catalogue/features";

/**
 * U-01-T08: routes in the route registry must declare their feature key (or CORE). Runs the rule
 * through the real eslint.config.mjs (the CI `eslint` step) on sample registries, then on the
 * real one.
 */
const RULE = "numo9/route-feature";
const frontendDir = fileURLToPath(new URL("../..", import.meta.url));
const eslint = new ESLint({ cwd: frontendDir });
const ROUTES_FILE = "src/routing/routes.ts";

async function problems(code: string, filePath = ROUTES_FILE): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath });
  return result!.messages.filter((m) => m.ruleId === RULE).map((m) => m.message);
}

const registry = (entries: string) =>
  `const CORE = "@core";\nexport const ORG_MODULES = [\n${entries}\n] as const;\n`;

describe("numo9/route-feature (U-01-T08)", () => {
  it("fails on a route without feature metadata", async () => {
    const found = await problems(registry(`  { path: "payroll/pay-runs", aliases: [] },`));
    expect(found).toHaveLength(1);
    expect(found[0]).toContain("Route 'payroll/pay-runs' declares no feature");
  });

  it.each([
    ["a malformed key", `"payroll.pay_runs"`],
    ["an unknown action", `"payroll.pay_runs.view"`],
    ["an empty string", `""`],
    ["a template literal", "`payroll.${area}.read`"],
  ])("fails on %s", async (_case, value) => {
    const found = await problems(
      registry(`  { path: "payroll/pay-runs", aliases: [], feature: ${value} },`),
    );
    expect(found).toHaveLength(1);
    expect(found[0]).toContain("Route 'payroll/pay-runs' has feature");
  });

  it("accepts keys, the @core literal and the CORE constant", async () => {
    const code = registry(
      [
        `  { path: "payroll/pay-runs", aliases: [], feature: "payroll.pay_runs.read" },`,
        `  { path: "commerce", aliases: [], feature: "app.commerce.orders.write" },`,
        `  { path: "home", aliases: [], feature: "@core" },`,
        `  { path: "settings", aliases: [], feature: CORE },`,
      ].join("\n"),
    );
    expect(await problems(code)).toEqual([]);
  });

  it("only checks the registry variables", async () => {
    expect(await problems(`export const OTHER = [{ path: "x" }];\n`)).toEqual([]);
  });

  it("the real route registry passes and every module declares a feature", async () => {
    const [result] = await eslint.lintFiles([ROUTES_FILE]);
    expect(result!.messages.filter((m) => m.ruleId === RULE)).toEqual([]);
    for (const entry of ORG_MODULES) {
      expect(entry.feature === CORE || isFeatureKey(entry.feature)).toBe(true);
    }
    expect(ORG_MODULES.find((m) => m.path === "accounting/journals")?.feature).toBe(
      "accounting.journals.read",
    );
  });
});
