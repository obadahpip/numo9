import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { contrastRatio, evaluatePairs, luminance } from "./contrast.mjs";
import { loadTokens } from "./build-tokens.mjs";
import { flatten } from "./tokens-lib.mjs";

const CLI = join(__dirname, "check-contrast.mjs");

describe("contrast maths (WCAG 2.1)", () => {
  it("black on white is 21:1 and order does not matter", () => {
    expect(contrastRatio("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
    expect(contrastRatio("#FFFFFF", "#000000")).toBeCloseTo(21, 5);
    expect(contrastRatio("#777777", "#777777")).toBeCloseTo(1, 5);
  });

  it("matches published reference values", () => {
    expect(contrastRatio("#767676", "#FFFFFF")).toBeCloseTo(4.54, 2); // lightest AA grey on white
    expect(contrastRatio("#777777", "#FFFFFF")).toBeCloseTo(4.48, 2); // just fails AA
    expect(luminance("#FFFFFF")).toBeCloseTo(1, 5);
  });

  it("rejects malformed and translucent colours", () => {
    expect(() => luminance("#FFF")).toThrow(/#rrggbb/);
    expect(() => luminance("#11111180")).toThrow(/translucent/);
    expect(luminance("#111111FF")).toBeCloseTo(luminance("#111111"), 10);
  });
});

describe("evaluatePairs", () => {
  const tokens = flatten({
    color: {
      $type: "color",
      ink: { $value: "#111111" },
      paper: { $value: "#FFFFFF" },
      sun: { $value: "#FFD100" },
    },
    space: { $type: "dimension", one: { $value: "4px" } },
  });

  it("passes and fails pairs against minRatio", () => {
    const results = evaluatePairs(tokens, {
      minRatio: 4.5,
      pairs: [
        { foreground: "color.ink", background: "color.sun" },
        { foreground: "color.sun", background: "color.paper" },
      ],
    });
    expect(results.map((r) => r.pass)).toEqual([true, false]);
    expect(results[1]?.ratio).toBeCloseTo(1.46, 2);
  });

  it("names unknown and non-colour tokens", () => {
    expect(() =>
      evaluatePairs(tokens, { pairs: [{ foreground: "color.nope", background: "color.paper" }] }),
    ).toThrow(/unknown token "color.nope"/);
    expect(() =>
      evaluatePairs(tokens, { pairs: [{ foreground: "space.one", background: "color.paper" }] }),
    ).toThrow(/not a colour/);
  });
});

describe("Numo9 tokens (A-10-T04 acceptance)", () => {
  it("every declared pair is at least 4.5:1", async () => {
    const pairs = (await import("../tokens/contrast-pairs.json")).default;
    const results = evaluatePairs(loadTokens(), pairs);
    expect(pairs.minRatio).toBe(4.5);
    expect(results.length).toBeGreaterThan(30);
    expect(results.filter((r) => !r.pass)).toEqual([]);
  });

  it("includes the yellow/black brand pairs and excludes yellow text on white", async () => {
    const pairs = (await import("../tokens/contrast-pairs.json")).default.pairs;
    const has = (fg: string, bg: string) =>
      pairs.some((p) => p.foreground === `semantic.${fg}` && p.background === `semantic.${bg}`);
    expect(has("text.onAccent", "surface.accent")).toBe(true);
    expect(has("text.inverseAccent", "surface.inverse")).toBe(true);
    expect(has("text.inverseAccent", "surface.default")).toBe(false);
  });
});

describe("check-contrast CLI", () => {
  const run = (...args: string[]) =>
    spawnSync(process.execPath, [CLI, ...args], { encoding: "utf8" });

  it("exits 0 on the committed tokens", () => {
    const result = run();
    expect(result.status).toBe(0);
    expect(result.stderr).toMatch(/all \d+ pairs ≥ 4.5:1/);
  });

  it("exits 1 when a pair fails, and 2 on a broken pair file", () => {
    const dir = mkdtempSync(join(tmpdir(), "n9-contrast-"));
    const tokensFile = join(dir, "tokens.json");
    writeFileSync(
      tokensFile,
      JSON.stringify({
        color: { $type: "color", sun: { $value: "#FFD100" }, paper: { $value: "#FFFFFF" } },
      }),
    );
    const failing = join(dir, "failing.json");
    writeFileSync(
      failing,
      JSON.stringify({
        minRatio: 4.5,
        pairs: [{ foreground: "color.sun", background: "color.paper" }],
      }),
    );
    const broken = join(dir, "broken.json");
    writeFileSync(
      broken,
      JSON.stringify({ pairs: [{ foreground: "color.none", background: "color.paper" }] }),
    );

    const fail = run("--tokens", tokensFile, "--pairs", failing);
    expect(fail.status).toBe(1);
    expect(fail.stdout).toMatch(/FAIL\s+1\.46:1/);
    expect(run("--tokens", tokensFile, "--pairs", broken).status).toBe(2);
  });

  it("prints a Markdown table with --markdown", () => {
    const result = run("--markdown");
    expect(result.stdout.split("\n")[0]).toBe(
      "| Foreground | Background | Colours | Ratio | Use |",
    );
  });
});
