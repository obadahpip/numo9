import path from "node:path";

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

import { headerRules } from "./src/security/headers";

// next-intl (A-10-T13): request config with the locale and ICU catalogues.
const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Design-system workspace package (A-10): shipped as TypeScript/CSS source, compiled by Next.
  transpilePackages: ["@numo9/ui"],
  // Self-contained server bundle for the Docker runtime image. Opt-in via NEXT_OUTPUT=standalone
  // (set in frontend/Dockerfile) because standalone tracing creates symlinks, which plain
  // Windows hosts cannot create without Developer Mode.
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" as const } : {}),
  // pnpm workspace: trace dependencies from the repository root.
  outputFileTracingRoot: path.join(process.cwd(), ".."),
  // Security headers on every route (S-03-T10); pages add their nonce CSP in the middleware.
  headers: async () => headerRules(process.env.NODE_ENV === "production"),
};

export default withNextIntl(nextConfig);
