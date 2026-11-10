import { readdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * A-10-T20 — usage-docs coverage: every component stories file (except the token foundations,
 * which document themselves) is embedded in a Guidelines page, and every Guidelines page but the
 * introduction has at least one do / don't pair.
 */
// `import.meta.url` is the module's file URL under Vitest; resolve paths with node:path (jsdom
// replaces the global URL).
const docsDir = dirname(fileURLToPath(import.meta.url));
const src = resolve(docsDir, "..");

const pages = readdirSync(docsDir)
  .filter((name) => name.endsWith(".mdx"))
  .map((name) => ({ name, text: readFileSync(`${docsDir}/${name}`, "utf8") }));

const storiesFiles = readdirSync(src, { recursive: true, encoding: "utf8" })
  .filter((p) => p.endsWith(".stories.tsx") && !p.startsWith("foundations"))
  .map((p) => p.replaceAll("\\", "/").replace(/\.tsx$/, ""));

describe("Storybook usage docs (A-10-T20)", () => {
  it("has the introduction, the microcopy rules and one page per component group", () => {
    expect(pages.map((p) => p.name).sort()).toEqual([
      "DataGrids.mdx",
      "FormsAndPickers.mdx",
      "Introduction.mdx",
      "Layout.mdx",
      "Microcopy.mdx",
      "Primitives.mdx",
      "States.mdx",
    ]);
  });

  it.each(storiesFiles)("embeds %s in a Guidelines page", (stories) => {
    expect(pages.some((p) => p.text.includes(`"../${stories}"`))).toBe(true);
  });

  it("gives every component page do / don't pairs", () => {
    for (const page of pages.filter((p) => p.name !== "Introduction.mdx")) {
      expect(page.text, page.name).toContain("<Do>");
      expect(page.text, page.name).toContain("<Dont>");
    }
  });
});
