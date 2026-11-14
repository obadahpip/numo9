"use client";

import { Badge, ErrorState, ExplainPanel, Input, LoadingRegion, SkeletonTable } from "@numo9/ui";
import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { PermissionExplain } from "@/components/PermissionExplain";
import { defineMessages, useFormatMessage } from "@/i18n";
import type { ApiError } from "@/settings/users-roles/api";

import { getOrganisationMatrix, isCatalogueError, type OrganisationMatrix } from "./api";

export const matrixMessages = defineMessages({
  title: {
    id: "catalogue.matrix.title",
    defaultMessage: "Package and features",
    description: "Heading of the in-app feature matrix page",
  },
  intro: {
    id: "catalogue.matrix.intro",
    defaultMessage:
      "What each package includes, product by product. Everything in a product is included together — approvals, reminders and history are never sold separately.",
    description: "Text under the heading",
  },
  search: {
    id: "catalogue.matrix.search",
    defaultMessage: "Search features",
    description: "Label of the search box",
  },
  searchHint: {
    id: "catalogue.matrix.searchHint",
    defaultMessage: "For example: reminder, approve, payroll",
    description: "Placeholder of the search box",
  },
  feature: { id: "catalogue.matrix.feature", defaultMessage: "Feature", description: "Column" },
  included: {
    id: "catalogue.matrix.included",
    defaultMessage: "Included in {package}",
    description: "Accessible text of a tick",
  },
  notIncluded: {
    id: "catalogue.matrix.notIncluded",
    defaultMessage: "Not in {package}",
    description: "Accessible text of a dash",
  },
  youAreHere: {
    id: "catalogue.matrix.youAreHere",
    defaultMessage: "You are here",
    description: "Badge on the organisation's current package column",
  },
  free: {
    id: "catalogue.matrix.free",
    defaultMessage: "Free for every practice and organisation",
    description: "Note on free product sets (Practice, Portal)",
  },
  readKept: {
    id: "catalogue.matrix.readKept",
    defaultMessage: "Kept after a downgrade",
    description: "Badge on read features: history stays viewable",
  },
  noPackages: {
    id: "catalogue.matrix.noPackages",
    defaultMessage:
      "Packages and prices aren't published yet. Every feature below belongs to the product named in its section.",
    description: "Shown while no package exists (before the Platform Owner creates them)",
  },
  results: {
    id: "catalogue.matrix.results",
    defaultMessage:
      "{count, plural, =0 {No features match “{query}”.} one {# feature matches “{query}”.} other {# features match “{query}”.}}",
    description: "Live search result count",
  },
  loading: {
    id: "catalogue.matrix.loading",
    defaultMessage: "Loading the feature matrix…",
    description: "Loading state",
  },
  loadFailed: {
    id: "catalogue.matrix.loadFailed",
    defaultMessage: "The feature matrix couldn't be loaded",
    description: "Error state title",
  },
  loadFailedBody: {
    id: "catalogue.matrix.loadFailedBody",
    defaultMessage: "Verify your connection, then try again.",
    description: "Error state text",
  },
  retry: { id: "catalogue.matrix.retry", defaultMessage: "Try again", description: "Button" },
  notFound: {
    id: "catalogue.matrix.notFound",
    defaultMessage: "This organisation isn't available",
    description: "The organisation doesn't exist or the person can't open it",
  },
});

/** Visual marks only (aria-hidden); the accessible text is the translated sentence beside them. */
const TICK = "\u2713";
const DASH = "\u2014";

const normalise = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase();

/**
 * Settings → Package and features (U-01-T12), `/o/:org/settings/package-features`: the in-app
 * feature matrix for everyone in the organisation (owners, staff, accountants — gap-41/61).
 * Searchable, grouped by product, a tick per package and the organisation's current package
 * highlighted ("You are here"). Packages come from U-02 and the current package from U-03/U-04;
 * until then the page lists every feature under its product.
 */
export function PackageFeaturesScreen({ org }: { org: string }) {
  const fm = useFormatMessage();
  const searchId = useId();
  const [matrix, setMatrix] = useState<OrganisationMatrix | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [missing, setMissing] = useState<ApiError | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setFailed(false);
    const { status, body } = await getOrganisationMatrix(org);
    if (status === 403) setError(isCatalogueError(body) ? body : {});
    else if (status === 404) setMissing(isCatalogueError(body) ? body : {});
    else if (status !== 200 || isCatalogueError(body)) setFailed(true);
    else setMatrix(body);
  }, [org]);

  useEffect(() => {
    void load();
  }, [load]);

  const groups = useMemo(() => {
    if (!matrix) return [];
    const words = normalise(query).split(/\s+/).filter(Boolean);
    return matrix.products
      .filter((p) => p.feature_count > 0)
      .map((product) => ({
        product,
        rows: matrix.features.filter((row) => {
          if (row.product !== product.code) return false;
          const text = normalise(`${row.description} ${row.key} ${row.product_name}`);
          return words.every((word) => text.includes(word));
        }),
      }))
      .filter((group) => group.rows.length > 0);
  }, [matrix, query]);

  if (error) return <PermissionExplain org={org} error={error} headingLevel={1} />;
  if (missing) {
    return (
      <ExplainPanel
        kind="notFound"
        headingLevel={1}
        title={fm(matrixMessages.notFound)}
        body={<p>{missing.detail}</p>}
      />
    );
  }
  if (failed) {
    return (
      <ErrorState
        title={fm(matrixMessages.loadFailed)}
        body={fm(matrixMessages.loadFailedBody)}
        retryLabel={fm(matrixMessages.retry)}
        onRetry={() => void load()}
      />
    );
  }

  const packages = matrix?.packages ?? [];
  const current = matrix?.current_package ?? null;
  const shown = groups.reduce((sum, g) => sum + g.rows.length, 0);

  return (
    <div className="flex min-w-0 flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{fm(matrixMessages.title)}</h1>
        <p className="max-w-3xl text-fg-muted">{fm(matrixMessages.intro)}</p>
      </header>
      <div className="flex max-w-md flex-col gap-1">
        <label htmlFor={searchId} className="text-sm font-medium">
          {fm(matrixMessages.search)}
        </label>
        <Input
          id={searchId}
          type="search"
          value={query}
          placeholder={fm(matrixMessages.searchHint)}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <p role="status" className="text-sm text-fg-muted">
        {query.trim() ? fm(matrixMessages.results, { count: shown, query: query.trim() }) : ""}
      </p>
      {matrix === null ? (
        <LoadingRegion label={fm(matrixMessages.loading)}>
          <SkeletonTable rows={8} columns={4} />
        </LoadingRegion>
      ) : null}
      {matrix && packages.length === 0 ? (
        <p className="rounded-md border border-border bg-surface-muted p-4 text-sm">
          {fm(matrixMessages.noPackages)}
        </p>
      ) : null}
      {groups.map(({ product, rows }) => {
        const headingId = `matrix-${product.code}`;
        return (
          <section
            key={product.code}
            aria-labelledby={headingId}
            data-product={product.code}
            className="min-w-0"
          >
            <div className="mb-2 flex flex-wrap items-baseline gap-2">
              <h2 id={headingId} className="text-lg font-semibold">
                {product.name}
              </h2>
              {!product.billable ? (
                <span className="text-sm text-fg-muted">{fm(matrixMessages.free)}</span>
              ) : null}
            </div>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm" aria-labelledby={headingId}>
                <thead className="bg-surface-muted text-fg-muted">
                  <tr>
                    <th scope="col" className="px-4 py-2 text-start font-medium">
                      {fm(matrixMessages.feature)}
                    </th>
                    {packages.map((pkg) => (
                      <th
                        key={pkg.code}
                        scope="col"
                        data-package={pkg.code}
                        data-current={pkg.code === current ? "true" : undefined}
                        aria-current={pkg.code === current ? "true" : undefined}
                        className={
                          pkg.code === current
                            ? "bg-surface-accent-subtle px-4 py-2 text-center font-semibold text-fg"
                            : "px-4 py-2 text-center font-medium"
                        }
                      >
                        <span className="flex flex-col items-center gap-1">
                          {pkg.name}
                          {pkg.code === current ? (
                            <Badge tone="accent">{fm(matrixMessages.youAreHere)}</Badge>
                          ) : null}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.key} data-feature-key={row.key} className="border-t border-border">
                      <th scope="row" className="px-4 py-2 text-start font-normal">
                        <span className="flex flex-wrap items-center gap-2">
                          {row.description}
                          {row.is_read_only ? (
                            <Badge tone="neutral">{fm(matrixMessages.readKept)}</Badge>
                          ) : null}
                        </span>
                      </th>
                      {packages.map((pkg) => {
                        const included = row.packages.includes(pkg.code);
                        const text = fm(
                          included ? matrixMessages.included : matrixMessages.notIncluded,
                          {
                            package: pkg.name,
                          },
                        );
                        return (
                          <td
                            key={pkg.code}
                            data-package={pkg.code}
                            className={
                              pkg.code === current
                                ? "relative bg-surface-accent-subtle px-4 py-2 text-center"
                                : "relative px-4 py-2 text-center"
                            }
                          >
                            <span
                              aria-hidden="true"
                              className={included ? "text-fg" : "text-fg-muted"}
                            >
                              {included ? TICK : DASH}
                            </span>
                            {/* relative cell: the sr-only text stays inside the scrolling table */}
                            <span className="sr-only">{text}</span>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </div>
  );
}
