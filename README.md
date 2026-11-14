# Numo9

**Numo9** — "Numbers build a brighter tomorrow". A Canadian, package-based accounting and practice
SaaS built by Gray Matter AI for Profitex. Django 5 API (`backend/`), Next.js 15 web app
(`frontend/`), design system (`packages/ui/`), Expo app (`mobile/`), infrastructure (`infra/`).

| Read                                                       | For                                                                                            |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| [Documentation home](docs/index.md)                        | Architecture, decisions, design, security, phase plans (`make docs-serve`)                     |
| [Contributing](CONTRIBUTING.md)                            | Local setup, the engineering workflow, branches, commits, pull requests                        |
| [Feature keys — developer guide](docs/dev/feature-keys.md) | How every endpoint and screen declares the feature key it needs, and how to test gating (U-01) |
| [Branch policy](docs/branching.md)                         | Protected `main`, branch naming, releases                                                      |

```bash
make up        # dev stack: Postgres, Redis, MinIO, Mailpit, ClamAV, backend, frontend
make help      # every developer command
```
