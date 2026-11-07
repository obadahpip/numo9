# mobile — Numo9 native apps (placeholder)

This pnpm workspace exists so CI paths and workspace commands include `mobile/` from Phase 0 (S-01-T05).

- No Expo project, dependencies, bundle identifiers or store credentials exist yet.
- Phase 7 (Y-01) initialises the Expo managed-workflow app here and pins the Expo SDK in `package.json`.
- `build`, `typecheck` and `test` scripts are no-op placeholders that succeed.
- Release tags for mobile are reserved as `mobile-vX.Y.Z`.

Install every workspace from the repository root with `pnpm install` (or `pnpm install --frozen-lockfile` in CI).
Note: `pnpm -w install` succeeds but installs only the workspace root's own dependencies.
