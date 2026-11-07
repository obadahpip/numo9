/**
 * i18n lint rules (S-01-T10). Used on its own by the CI i18n job
 * (`pnpm run lint:i18n`) and included in the main eslint.config.mjs.
 */
import tsParser from "@typescript-eslint/parser";
import formatjs from "eslint-plugin-formatjs";

const i18nConfig = [
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

export default i18nConfig;
