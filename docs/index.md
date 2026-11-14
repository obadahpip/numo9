# Numo9 documentation

**Numo9** — "Numbers build a brighter tomorrow". A Canadian, package-based accounting and practice
SaaS built by Gray Matter AI for Profitex.

| Start here | What it covers |
|---|---|
| [Contributing](contributing.md) | Local setup, the engineering workflow, branches, commits, pull requests |
| [Branch policy](branching.md) | Protected `main`, branch naming, release tags, Dependabot exception |
| [Architecture decisions](adr/index.md) | Why the system is built the way it is (ADRs) |
| [Brand tokens](design/brand-tokens.md) | Colour, type, spacing, radius and elevation tokens; accessible yellow/black pairs |
| [Phase 0 wireframes](design/wireframes.md) | Shell, directory, settings, contacts, chart of accounts, journal, console |
| [Tenancy model](architecture/tenancy.md) | Practices, organisations, access rule and the isolation layers |
| [Feature keys — developer guide](dev/feature-keys.md) | Declaring the feature key of every endpoint and screen, testing gating (U-01) |
| [Data-residency register](security/data-residency-register.md) | Where every data class lives and every sub-processor (ADR-0002) |
| [Project plan](Numo9_Project_Plan.md) | Scope, components, acceptance and the gap analysis against Xero |
| [Phase plans](phase_plans/Phase_0_Foundation_and_SaaS_Core.md) | Deliverables and atomic tasks, phase by phase |

## Repository layout

```text
backend/    Django 5.2 API and workers
frontend/   Next.js 15 web app (App Router, TypeScript strict)
mobile/     Expo workspace (Phase 7)
packages/   shared workspace packages — ui/ is the @numo9/ui design system (A-10)
infra/      deploy scripts, staging stack
docs/       this site (MkDocs Material)
tools/      repository tooling (CI, pre-commit helpers)
```

## Delivery flow

```mermaid
flowchart LR
  task[Atomic task issue] --> branch[Branch from main]
  branch --> pr[Pull request + Rule 10 report]
  pr --> ci{CI and security checks}
  ci -- green + 1 review --> main[(main)]
  main -- tag vX.Y.Z --> staging[Staging deploy]
  staging -- approval --> prod[Production deploy]
```
