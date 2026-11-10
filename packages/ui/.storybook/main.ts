import type { StorybookConfig } from "@storybook/react-vite";
import tailwindcss from "@tailwindcss/vite";

/** Storybook 8 for @numo9/ui (A-10-T03). `pnpm --filter @numo9/ui run storybook` */
const config: StorybookConfig = {
  // Usage docs (do / don't, microcopy rules) live in src/docs/*.mdx (A-10-T20).
  stories: ["../src/docs/*.mdx", "../src/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-essentials", "@storybook/addon-a11y"],
  framework: { name: "@storybook/react-vite", options: {} },
  core: { disableTelemetry: true },
  async viteFinal(viteConfig) {
    viteConfig.plugins = [...(viteConfig.plugins ?? []), tailwindcss()];
    // `"use client"` marks components for Next.js; Vite reports it as an ignored directive.
    viteConfig.build = {
      ...viteConfig.build,
      rollupOptions: {
        ...viteConfig.build?.rollupOptions,
        onwarn(warning, warn) {
          if (warning.code === "MODULE_LEVEL_DIRECTIVE" || warning.code === "SOURCEMAP_ERROR")
            return;
          warn(warning);
        },
      },
    };
    return viteConfig;
  },
};

export default config;
