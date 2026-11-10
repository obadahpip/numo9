// @vitest-environment node
import { fileURLToPath } from "node:url";

import { ESLint } from "eslint";

import numo9 from "../../eslint/no-work-screen-banners.mjs";

/**
 * A-10-T17 / gap-12: no promotional or announcement banners inside editor and list layouts;
 * notices go to the notification centre. Runs the rule through the real eslint.config.mjs (the
 * CI `eslint` step) on sample screens, then over the whole frontend and design-system source.
 */
const RULE = "numo9/no-work-screen-banners";
const frontendDir = fileURLToPath(new URL("../..", import.meta.url));
const repoDir = fileURLToPath(new URL("../../..", import.meta.url));
const eslint = new ESLint({ cwd: frontendDir });

async function bannerProblems(code: string, filePath: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath });
  return result!.messages.filter((m) => m.ruleId === RULE).map((m) => m.message);
}

const EDITOR = "src/app/o/[org]/sales/invoices/new/page.tsx";
const LIST = "src/app/o/[org]/contacts/page.tsx";

describe("gap-12: no banners in work screens (A-10-T17)", () => {
  it.each([
    ["a *Banner component in an editor", `<UpgradeBanner />`, EDITOR],
    ["a Promo* component in a list", `<PromoCard />`, LIST],
    ["a namespaced marketing component", `<Marketing.Hero />`, LIST],
    ["an Announcement* component", `<AnnouncementStrip />`, EDITOR],
    ["role=banner", `<div role="banner" />`, EDITOR],
    ["a promo class", `<section className="promo-card mt-4" />`, LIST],
    ["a banner class in a template literal", "<div className={`banner ${tone}`} />", LIST],
    ["a data-promo attribute", `<aside data-promo="payroll" />`, EDITOR],
  ])("rejects %s", async (_case, jsx, file) => {
    const code = `const tone = "x";\nexport const Screen = () => (${jsx});\n`;
    const problems = await bannerProblems(code, file);
    expect(problems).toHaveLength(1);
    expect(problems[0]).toContain("gap-12");
    expect(problems[0]).toContain("notification centre");
  });

  it("allows commercial messages in Settings → Subscription and the Home announcement slot", async () => {
    const code = `export const S = () => <UpgradeBanner className="promo-card" />;\n`;
    expect(await bannerProblems(code, "src/app/o/[org]/settings/subscription/page.tsx")).toEqual(
      [],
    );
    expect(
      await bannerProblems(code, "src/components/announcements/HomeAnnouncementSlot.tsx"),
    ).toEqual([]);
  });

  it("does not flag ordinary components and classes", async () => {
    const code =
      `export const S = () => (<><AdvancedFilter /><Address /><AddButton />` +
      `<div className="bannerless promotion-free" role="region" /><header /></>);\n`;
    expect(await bannerProblems(code, EDITOR)).toEqual([]);
  });

  it("finds no banner in the frontend source", async () => {
    const results = await eslint.lintFiles(["src/**/*.{ts,tsx}"]);
    const problems = results.flatMap((r) =>
      r.messages.filter((m) => m.ruleId === RULE).map((m) => `${r.filePath}: ${m.message}`),
    );
    expect(problems).toEqual([]);
  });

  it("finds no banner in the design system (@numo9/ui) components", async () => {
    const ui = new ESLint({
      cwd: repoDir,
      overrideConfigFile: true,
      overrideConfig: [
        {
          files: ["packages/ui/src/**/*.tsx"],
          ignores: ["**/*.test.tsx"],
          languageOptions: {
            parser: (await import("@typescript-eslint/parser")).default,
            parserOptions: { ecmaFeatures: { jsx: true } },
          },
          plugins: { numo9 },
          rules: { [RULE]: "error" },
        },
      ],
    });
    const results = await ui.lintFiles(["packages/ui/src/**/*.tsx"]);
    expect(results.length).toBeGreaterThan(10);
    const problems = results.flatMap((r) =>
      r.messages.filter((m) => m.ruleId === RULE).map((m) => `${r.filePath}: ${m.message}`),
    );
    expect(problems).toEqual([]);
  });
});
