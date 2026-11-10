// @vitest-environment node
import { fileURLToPath } from "node:url";

import { ESLint } from "eslint";

/**
 * A-10-T13 acceptance: a hard-coded string fails lint. Runs the i18n eslint config (the same one
 * the CI i18n job and `pnpm lint` use) on sample components.
 */
const cwd = fileURLToPath(new URL("../..", import.meta.url));
const eslint = new ESLint({ cwd, overrideConfigFile: "eslint.i18n.config.mjs" });

async function lint(code: string) {
  const [result] = await eslint.lintText(code, { filePath: "src/components/Sample.tsx" });
  return result!.messages.map((message) => `${message.ruleId}: ${message.message}`);
}

describe("i18n lint (A-10-T13)", () => {
  it("rejects hard-coded text in JSX and in accessible attributes", async () => {
    expect(await lint(`export const A = () => <p>Save settings</p>;\n`)).toEqual([
      expect.stringContaining("formatjs/no-literal-string-in-jsx"),
    ]);
    expect(await lint(`export const B = () => <button aria-label="Close">x</button>;\n`)).toEqual(
      expect.arrayContaining([expect.stringContaining("formatjs/no-literal-string-in-jsx")]),
    );
    expect(await lint(`export const C = () => <input placeholder="Search" />;\n`)).toEqual([
      expect.stringContaining("formatjs/no-literal-string-in-jsx"),
    ]);
  });

  it("requires a description and a literal default message on every descriptor", async () => {
    const problems = await lint(
      `import { defineMessages } from "@/i18n";\n` +
        `export const m = defineMessages({ a: { id: "x.a", defaultMessage: "Hi" } });\n`,
    );
    expect(problems).toEqual([expect.stringContaining("formatjs/enforce-description")]);
  });

  it("accepts text that comes from messages", async () => {
    const code =
      `import { defineMessages, useFormatMessage } from "@/i18n";\n` +
      `const m = defineMessages({ save: { id: "x.save", defaultMessage: "Save settings", description: "Button" } });\n` +
      `export function A() {\n  const fm = useFormatMessage();\n  return <button aria-label={fm(m.save)}>{fm(m.save)}</button>;\n}\n`;
    expect(await lint(code)).toEqual([]);
  });
});
