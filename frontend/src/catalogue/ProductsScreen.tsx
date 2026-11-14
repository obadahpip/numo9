"use client";

import { Badge, Drawer, ExplainPanel, LoadingRegion, SkeletonTable, StatusBadge } from "@numo9/ui";
import { useEffect, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import {
  isCatalogueError,
  listConsoleProducts,
  matrixExportUrl,
  type CatalogueError,
  type ProductDetail,
} from "./api";

export const productMessages = defineMessages({
  title: {
    id: "catalogue.products.title",
    defaultMessage: "Products",
    description: "Heading of the platform console's Products screen",
  },
  intro: {
    id: "catalogue.products.intro",
    defaultMessage:
      "Everything Numo9 sells or gives, and the feature keys each product includes. Packages are made of whole products.",
    description: "Text under the Products heading",
  },
  product: { id: "catalogue.products.product", defaultMessage: "Product", description: "Column" },
  code: { id: "catalogue.products.code", defaultMessage: "Code", description: "Column" },
  kind: { id: "catalogue.products.kind", defaultMessage: "Kind", description: "Column" },
  status: { id: "catalogue.products.status", defaultMessage: "Status", description: "Column" },
  features: {
    id: "catalogue.products.features",
    defaultMessage: "Feature keys",
    description: "Column: number of feature keys",
  },
  free: {
    id: "catalogue.products.free",
    defaultMessage: "Free",
    description: "Badge: free product set, never billed",
  },
  showKeys: {
    id: "catalogue.products.showKeys",
    defaultMessage: "Show the feature keys of {product}",
    description: "Accessible name of the button opening a product's detail drawer",
  },
  companions: {
    id: "catalogue.products.companions",
    defaultMessage: "Companion apps",
    description: "Heading of the planned companion apps",
  },
  companionsIntro: {
    id: "catalogue.products.companionsIntro",
    defaultMessage: "Apps Numo9 will build. They can't be put in a package until they're active.",
    description: "Text under the companion apps heading",
  },
  drawerDescription: {
    id: "catalogue.products.drawerDescription",
    defaultMessage:
      "{count, plural, =0 {No feature keys yet.} one {# feature key} other {# feature keys}}",
    description: "Detail drawer: number of keys",
  },
  key: { id: "catalogue.products.key", defaultMessage: "Key", description: "Column" },
  description: {
    id: "catalogue.products.description",
    defaultMessage: "What it allows",
    description: "Column: plain-language description of a feature key",
  },
  readOnly: {
    id: "catalogue.products.readOnly",
    defaultMessage: "Read",
    description: "Badge: read key (kept after a downgrade)",
  },
  noKeys: {
    id: "catalogue.products.noKeys",
    defaultMessage: "Feature keys are added when this product is built.",
    description: "Detail drawer of a product without keys",
  },
  close: {
    id: "catalogue.products.close",
    defaultMessage: "Close",
    description: "Close the drawer",
  },
  exportCsv: {
    id: "catalogue.products.exportCsv",
    defaultMessage: "Export feature matrix (CSV)",
    description: "Download link",
  },
  exportXlsx: {
    id: "catalogue.products.exportXlsx",
    defaultMessage: "Export feature matrix (XLSX)",
    description: "Download link",
  },
  loading: {
    id: "catalogue.products.loading",
    defaultMessage: "Loading products…",
    description: "Loading state",
  },
  loadFailed: {
    id: "catalogue.products.loadFailed",
    defaultMessage: "The products couldn't be loaded. Refresh the page to try again.",
    description: "The request failed",
  },
  refusedTitle: {
    id: "catalogue.products.refusedTitle",
    defaultMessage: "You can't open the product catalogue",
    description: "Title when the person lacks platform.catalogue.view",
  },
});

/**
 * Platform console → Products (U-01-T11): the catalogue — main products and free sets with
 * status chips, planned companion apps greyed with "Planned", a detail drawer listing each
 * product's feature keys, and the feature-matrix export (T10).
 */
export function ProductsScreen() {
  const fm = useFormatMessage();
  const [products, setProducts] = useState<ProductDetail[] | null>(null);
  const [refusal, setRefusal] = useState<CatalogueError | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<ProductDetail | null>(null);

  useEffect(() => {
    void listConsoleProducts().then(({ status, body }) => {
      if (status === 401 || status === 403) setRefusal(isCatalogueError(body) ? body : {});
      else if (status !== 200 || isCatalogueError(body)) setFailed(true);
      else setProducts(body.products);
    });
  }, []);

  if (refusal) {
    return (
      <ExplainPanel
        kind="permission"
        headingLevel={1}
        title={fm(productMessages.refusedTitle)}
        body={<p>{refusal.detail}</p>}
      />
    );
  }

  const sellable = products?.filter((p) => p.kind !== "companion") ?? [];
  const companions = products?.filter((p) => p.kind === "companion") ?? [];

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold">{fm(productMessages.title)}</h1>
          <p className="text-fg-muted">{fm(productMessages.intro)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a className={LINK_BUTTON} href={matrixExportUrl("csv")} download>
            {fm(productMessages.exportCsv)}
          </a>
          <a className={LINK_BUTTON} href={matrixExportUrl("xlsx")} download>
            {fm(productMessages.exportXlsx)}
          </a>
        </div>
      </header>
      {failed ? (
        <p role="alert" className="text-fg-danger">
          {fm(productMessages.loadFailed)}
        </p>
      ) : null}
      {products === null && !failed ? (
        <LoadingRegion label={fm(productMessages.loading)}>
          <SkeletonTable rows={7} columns={5} />
        </LoadingRegion>
      ) : null}
      {products ? (
        <>
          <ProductTable rows={sellable} onOpen={setOpen} labelledBy="catalogue-products" />
          <section aria-labelledby="catalogue-companions" className="flex flex-col gap-3">
            <div>
              <h2 id="catalogue-companions" className="text-lg font-semibold">
                {fm(productMessages.companions)}
              </h2>
              <p className="text-sm text-fg-muted">{fm(productMessages.companionsIntro)}</p>
            </div>
            <ProductTable rows={companions} onOpen={setOpen} labelledBy="catalogue-companions" />
          </section>
        </>
      ) : null}
      <Drawer
        open={open !== null}
        onOpenChange={(next) => (next ? undefined : setOpen(null))}
        title={open?.name ?? ""}
        description={
          open ? fm(productMessages.drawerDescription, { count: open.features.length }) : undefined
        }
        closeLabel={fm(productMessages.close)}
        size="lg"
      >
        {open ? <FeatureList product={open} /> : null}
      </Drawer>
    </div>
  );
}

const LINK_BUTTON =
  "inline-flex items-center rounded-md border border-border bg-surface px-3 py-2 text-sm font-medium text-fg hover:bg-surface-muted";

function ProductTable({
  rows,
  onOpen,
  labelledBy,
}: {
  rows: ProductDetail[];
  onOpen: (product: ProductDetail) => void;
  labelledBy: string;
}) {
  const fm = useFormatMessage();
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-start text-sm" aria-labelledby={labelledBy}>
        {labelledBy === "catalogue-products" ? (
          <caption id="catalogue-products" className="sr-only">
            {fm(productMessages.title)}
          </caption>
        ) : null}
        <thead className="bg-surface-muted text-fg-muted">
          <tr>
            <th scope="col" className="px-4 py-2 text-start font-medium">
              {fm(productMessages.product)}
            </th>
            <th scope="col" className="px-4 py-2 text-start font-medium">
              {fm(productMessages.code)}
            </th>
            <th scope="col" className="px-4 py-2 text-start font-medium">
              {fm(productMessages.kind)}
            </th>
            <th scope="col" className="px-4 py-2 text-start font-medium">
              {fm(productMessages.status)}
            </th>
            <th scope="col" className="px-4 py-2 text-end font-medium">
              {fm(productMessages.features)}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((product) => {
            const planned = product.status === "planned";
            return (
              <tr
                key={product.code}
                data-product={product.code}
                data-status={product.status}
                className={
                  planned ? "border-t border-border text-fg-muted" : "border-t border-border"
                }
              >
                <td className="px-4 py-2">
                  <button
                    type="button"
                    className="font-medium underline-offset-2 hover:underline"
                    aria-label={fm(productMessages.showKeys, { product: product.name })}
                    onClick={() => onOpen(product)}
                  >
                    {product.name}
                  </button>
                  {!product.billable ? (
                    <Badge tone="info" className="ms-2">
                      {fm(productMessages.free)}
                    </Badge>
                  ) : null}
                </td>
                <td className="px-4 py-2 font-mono text-xs">{product.code}</td>
                <td className="px-4 py-2">{product.kind_label}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={product.status} label={product.status_label} />
                </td>
                <td className="px-4 py-2 text-end tabular-nums">{product.feature_count}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FeatureList({ product }: { product: ProductDetail }) {
  const fm = useFormatMessage();
  if (product.features.length === 0) {
    return <p className="text-fg-muted">{fm(productMessages.noKeys)}</p>;
  }
  return (
    // Focusable so keyboard users can scroll a long list (the drawer body has no other control).
    <ul
      tabIndex={0}
      className="flex flex-col divide-y divide-border rounded-md"
      aria-label={fm(productMessages.features)}
    >
      {product.features.map((feature) => (
        <li key={feature.key} className="flex flex-col gap-1 py-2" data-feature-key={feature.key}>
          <span className="flex items-center gap-2">
            <code className="font-mono text-xs">{feature.key}</code>
            {feature.is_read_only ? (
              <Badge tone="neutral">{fm(productMessages.readOnly)}</Badge>
            ) : null}
          </span>
          <span>{feature.description}</span>
        </li>
      ))}
    </ul>
  );
}
