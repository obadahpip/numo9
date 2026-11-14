import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { FlatCompat } from "@eslint/eslintrc";

import numo9, { BANNER_ALLOWED_FILES } from "./eslint/no-work-screen-banners.mjs";
import i18nConfig from "./eslint.i18n.config.mjs";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

const config = [
  {
    ignores: [".next/**", "node_modules/**", "coverage/**", "next-env.d.ts"],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  // No hard-coded strings; message descriptor rules (S-01-T10).
  ...i18nConfig,
  // No promotional/announcement banners inside work screens; notices go to the notification
  // centre (A-10-T17, gap-12).
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}"],
    plugins: { numo9 },
    rules: { "numo9/no-work-screen-banners": ["error", { allow: BANNER_ALLOWED_FILES }] },
  },
  // Every route in the route registry declares its feature key or CORE (U-01-T08).
  {
    files: ["src/routing/routes.ts"],
    plugins: { numo9 },
    rules: { "numo9/route-feature": ["error", { registries: ["ORG_MODULES"] }] },
  },
  // Must stay last: turns off rules that conflict with Prettier formatting.
  ...compat.extends("prettier"),
];

export default config;
