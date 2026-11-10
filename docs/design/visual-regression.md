# Visual regression

A-10-T18 · Deliverable A-10 · Deliverable acceptance: "visual regression passes".

Playwright screenshot comparison (no third-party service): every `@numo9/ui` story and every
Phase 0 page is captured and compared with a committed baseline on each pull request.

| Suite | What is captured | Baselines |
|---|---|---|
| Components — `packages/ui/e2e/visual.spec.ts` | Every story listed in the built Storybook's `index.json` (42 today), 1024 × 768 | `packages/ui/e2e/__screenshots__/visual.spec.ts/<story-id>.png` |
| Pages — `frontend/e2e/visual.spec.ts` | `/`, every Phase 0 organisation route and the 404 page, at 1280 px and 360 px, full page | `frontend/e2e/__screenshots__/visual.spec.ts/<page>-<width>.png` |

A new story or a new Phase 0 route is covered automatically. Tag a story `no-visual` only when
its output cannot be made deterministic (none today).

## Determinism

- Linux only: one baseline per screenshot (no platform suffix), produced on Ubuntu 24.04 with
  `fonts-inter` and `fonts-dejavu-core` and Playwright Chromium.
- Fixed clock (26 Oct 2026, 14:00 ET), CSS animations disabled, caret hidden, fonts awaited.
- Tolerance: per-pixel colour threshold 0.2 and at most 100 differing pixels — enough for
  anti-aliasing noise, small enough to catch a changed word, colour or 1 px shift.

## Commands

```bash
pnpm --filter @numo9/ui run build-storybook && pnpm --filter @numo9/ui run test:visual
pnpm --filter @numo9/frontend run build && pnpm --filter @numo9/frontend run test:visual

# after an intended visual change (Linux with fonts-inter):
pnpm --filter @numo9/ui run test:visual:update
pnpm --filter @numo9/frontend run test:visual:update
```

The `@visual` tests are excluded from `test:e2e` and run in the CI `visual` job. On failure the
job uploads `visual-diffs` (expected / actual / diff PNGs).

## Approving a baseline

1. Run **Actions → Visual baselines** (workflow_dispatch) on the branch; it regenerates every
   baseline on the CI runner image and uploads the `visual-baselines` artefact.
2. The project lead reviews the PNGs (GitHub shows image diffs in the pull request) and commits
   them. That commit is the approval; the `visual` job must then pass.
