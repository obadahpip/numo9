#!/usr/bin/env node
/**
 * check-contrast (A-10-T04): every token pair in tokens/contrast-pairs.json must reach the
 * WCAG 2.1 AA ratio (minRatio, 4.5:1). Exit code 1 if any pair fails.
 *
 *   node scripts/check-contrast.mjs                     table of all pairs
 *   node scripts/check-contrast.mjs --markdown          the same table as Markdown (for docs)
 *   node scripts/check-contrast.mjs --tokens a.json --pairs b.json
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { evaluatePairs } from "./contrast.mjs";
import { flatten } from "./tokens-lib.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const tokensFile = arg("--tokens", join(ROOT, "tokens", "tokens.json"));
const pairsFile = arg("--pairs", join(ROOT, "tokens", "contrast-pairs.json"));

let results;
try {
  const tokens = flatten(JSON.parse(readFileSync(tokensFile, "utf8")));
  results = evaluatePairs(tokens, JSON.parse(readFileSync(pairsFile, "utf8")));
} catch (error) {
  console.error(`check-contrast: ${error.message}`);
  process.exit(2);
}

const short = (path) => path.replace(/^semantic\./, "");
const ratio = (r) => `${r.ratio.toFixed(2)}:1`;
const failed = results.filter((r) => !r.pass);

if (process.argv.includes("--markdown")) {
  console.log("| Foreground | Background | Colours | Ratio | Use |");
  console.log("|---|---|---|---|---|");
  for (const r of results) {
    console.log(
      `| \`${short(r.foreground)}\` | \`${short(r.background)}\` | \`${r.fg}\` on \`${r.bg}\` | ${ratio(r)}${r.pass ? "" : " ✗"} | ${r.use} |`,
    );
  }
} else {
  for (const r of results) {
    const mark = r.pass ? "ok  " : "FAIL";
    console.log(
      `${mark} ${ratio(r).padStart(8)}  ${short(r.foreground)} on ${short(r.background)} (${r.fg} on ${r.bg})`,
    );
  }
}

const min = results[0]?.min ?? 4.5;
if (failed.length) {
  console.error(`check-contrast: ${failed.length} of ${results.length} pairs below ${min}:1`);
  process.exit(1);
}
console.error(`check-contrast: all ${results.length} pairs ≥ ${min}:1`);
