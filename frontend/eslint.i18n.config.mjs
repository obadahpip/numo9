/**
 * i18n lint rules (S-01-T10). Used on its own by the CI i18n job
 * (`pnpm run lint:i18n`) and included in the main eslint.config.mjs.
 */
import tsParser from "@typescript-eslint/parser";
import formatjs from "eslint-plugin-formatjs";

export const i18nConfig = [
  {
    ignores: [".next/**", "node_modules/**", "coverage/**", "next-env.d.ts"],
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { formatjs },
    rules: {
      // No hard-coded user-visible text in JSX children or accessible/text attributes.
      "formatjs/no-literal-string-in-jsx": [
        "error",
        {
          props: {
            include: [
              ["*", "{aria-label,aria-description,aria-placeholder,alt,title,placeholder,label}"],
            ],
          },
        },
      ],
      "formatjs/enforce-default-message": ["error", "literal"],
      "formatjs/enforce-description": ["error", "literal"],
      "formatjs/no-multiple-whitespaces": "error",
    },
  },
];

/**
 * Run on its own, this config has no react-hooks plugin: a stub keeps the source's
 * `eslint-disable-next-line react-hooks/exhaustive-deps` comments from failing as unknown rules.
 * The main eslint.config.mjs imports `i18nConfig` (the real plugin comes from next there).
 */
const reactHooksStub = {
  rules: { "exhaustive-deps": { meta: { schema: [] }, create: () => ({}) } },
};

const standaloneConfig = [
  ...i18nConfig,
  {
    plugins: { "react-hooks": reactHooksStub },
    linterOptions: { reportUnusedDisableDirectives: "off" },
  },
];

export default standaloneConfig;
