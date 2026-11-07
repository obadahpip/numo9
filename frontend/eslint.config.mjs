import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { FlatCompat } from "@eslint/eslintrc";

import i18nConfig from "./eslint.i18n.config.mjs";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

const config = [
  {
    ignores: [".next/**", "node_modules/**", "coverage/**", "next-env.d.ts"],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  // No hard-coded strings; message descriptor rules (S-01-T10).
  ...i18nConfig,
  // Must stay last: turns off rules that conflict with Prettier formatting.
  ...compat.extends("prettier"),
];

export default config;
