# Feature keys — developer guide (U-01-T15)

Numo9 is sold as packages made of products (Accounting, Tax, Payroll, Inventory, Finance; Practice
and Portal are free). Every **gated** endpoint and screen declares the **feature key** it needs;
the entitlement engine (U-03) decides whether the active organisation's package includes it.
Design and data model: [Product catalogue and feature keys](../architecture/feature-keys.md).

!!! note "Until U-03 ships"
    The entitlement resolver is a stub that allows every key, and the web app's entitlement source
    allows every feature. Declaring keys now costs nothing at runtime and makes every endpoint and
    screen ready for gating the day the engine is switched on.

## 1. Choose the key

A key is `<product>.<area>.<action>`, action `read`, `write` or `approve`:

| You are building | Declare |
|---|---|
| a list, a detail page, a report, an export of the area | `<product>.<area>.read` |
| create / edit / send / void / import in the area | `<product>.<area>.write` |
| an approval, posting or authorisation step | `<product>.<area>.approve` |
| something every organisation has: sign-in, organisation settings, users and roles, approval limits, lock dates, audit log, jobs, notifications | `CORE` (no key — never gated) |

- Look the key up first: `GET /api/v1/catalogue/feature-matrix`,
  `manage.py featurematrix_export`, or the seed in
  `backend/numo9/catalogue/migrations/0003_seed_catalogue.py`. Reuse the area's key for
  sub-features (attachments, PDF, email of the same document).
- Inside one product nothing is gated separately: approving invoices, credit notes, reminders,
  bank accounts are all part of Accounting. Never invent a key to sell a control separately
  (gap-06, gap-41).

### Adding a new key

Keys are data. A new area (or a later phase's product keys) is added with a **data migration**
in the owning app, plus its description:

1. `backend/numo9/<app>/migrations/00NN_feature_keys.py` — `RunPython` that `get_or_create`s the
   `catalogue.FeatureKey` rows (`key`, `product`, `description_i18n_key =
   "catalogue.feature.<key>"`, `is_read_only = key.endswith(".read")`); depend on
   `("catalogue", "0003_seed_catalogue")`.
2. `backend/numo9/catalogue/texts.py` — add `"catalogue.feature.<key>": _("Plain language for an
   organisation owner")` (what it lets them do, sentence case, no full stop), then `make i18n`.
3. Rewrite the web app's fixtures: `NUMO9_WRITE_FIXTURES=1 pytest tests/test_catalogue_fixtures.py`.

`tests/test_catalogue_texts.py` fails when a key has no description; the database refuses a key
declared twice (unique index) or one whose prefix is not its product's code.

## 2. Declare it on the endpoint (Django REST framework)

```python
from numo9.catalogue.drf import CORE, requires_feature
from numo9.rbac.drf import requires_permission


class InvoiceListView(APIView):
    @requires_permission("sales.invoice.view")          # who may (A-03)
    @requires_feature("accounting.sales_invoices.read")  # which product (U-01)
    def get(self, request, org): ...

    @requires_permission("sales.invoice.create")
    @requires_feature("accounting.sales_invoices.write")
    def post(self, request, org): ...


class LockDatesView(APIView):
    required_feature = CORE  # every method; or {"GET": "...read", "POST": "...write"}
```

- `RequiresFeature` is a default permission class, after `RequiresPermission`: a foreign
  organisation answers 404, a missing permission 403, and then a key outside the package
  **402** `entitlement.feature_not_in_package` with `feature` and `product` in the body. A view
  that sets its own `permission_classes` must list `numo9.catalogue.drf.RequiresFeature`.
- Business endpoints are the organisation and practice routes (`/api/v1/o/<org>/…`,
  `/api/v1/p/<practice>/…`, setting `FEATURE_BUSINESS_ROUTES`). Each of their methods must declare
  a key or `CORE`. Other endpoints need no key, but a key they declare must exist.

### The CI gate

```bash
python manage.py migrate                 # the known keys are catalogue rows
python manage.py check_feature_keys      # every method, its key; fails on a problem
```

| Problem | Meaning |
|---|---|
| `feature.E001` | a business endpoint method declares nothing |
| `feature.E002` | a declared key is not in the catalogue (typo, or its data migration is missing) |
| `feature.E003` | a business view's `permission_classes` don't include `RequiresFeature` |

The CI backend job runs it, and a canary (`--urlconf tests.testapp.feature_urls_ci_canary`, an
undeclared business endpoint) that must fail — proving the gate turns CI red.

## 3. Declare it on the screen (Next.js)

Routes declare their key in the route registry (`frontend/src/routing/routes.ts`); eslint
`numo9/route-feature` fails a route without one:

```ts
{ path: "accounting/journals", feature: "accounting.journals.read", label: …, aliases: [] },
{ path: "settings/lock-dates", feature: CORE, label: …, aliases: [] },
```

Controls and panels use the hook or the wrapper (`@/catalogue/Gated`):

```tsx
import { Gated, useFeature } from "@/catalogue/Gated";

const invoices = useFeature("accounting.sales_invoices.write"); // { state, product, productName, packages }

<Gated feature="payroll.pay_runs.write" packagesHref={`/o/${org}/settings/package-features`}>
  <PayRunEditor />
</Gated>
```

A gated feature renders the locked panel **in place** — never hidden, never a redirect (gap-14).
Decisions come from the nearest `FeatureProvider` (the U-03 entitlement store); without one, every
feature is allowed.

## 4. Test the gating

Backend — point the resolver at a fake that refuses, and assert the 402:

```python
class DenyAll:
    def allows(self, organisation, key):
        return False


def test_invoices_need_accounting(settings, client):
    settings.NUMO9_ENTITLEMENT_RESOLVER = "tests.test_invoices.DenyAll"
    response = client.post(url, {...})
    assert response.status_code == 402
    assert response.json()["code"] == "entitlement.feature_not_in_package"
    assert response.json()["product"] == "accounting"
```

Frontend — wrap the component in a `FeatureProvider` whose source answers `gated`:

```tsx
renderWithIntl(
  <FeatureProvider source={(feature) => ({ feature, state: "gated", productName: "Payroll" })}>
    <Gated feature="payroll.pay_runs.write"><PayRuns /></Gated>
  </FeatureProvider>,
);
expect(screen.getByRole("heading", { name: "Payroll isn't in this organisation's package" }));
```

Examples in the repository: `backend/tests/test_requires_feature.py`,
`backend/tests/test_feature_key_ci_check.py`, `frontend/src/catalogue/Gated.test.tsx`,
`packages/ui/src/entitlements/Gated.test.tsx` and the Storybook stories *Entitlements/Gated*.

## Where to look

| What | Where |
|---|---|
| Products and keys (models, seed, texts) | `backend/numo9/catalogue/` |
| Decorator, permission class, `CORE` | `backend/numo9/catalogue/drf.py` |
| Resolver and package interfaces (stubs until U-02 / U-03) | `backend/numo9/catalogue/entitlements.py`, `packages.py` |
| APIs | `GET /api/v1/catalogue/products`, `/api/v1/catalogue/feature-matrix`, `/api/v1/o/<org>/package-features`, `/api/v1/platform/catalogue/products`, `/api/v1/platform/catalogue/feature-matrix/export/<csv\|xlsx>` |
| Commands | `check_feature_keys`, `featurematrix_export` |
| Screens | Platform console → Products (`/console/products`), Settings → Package and features (`/o/:org/settings/package-features`) |
