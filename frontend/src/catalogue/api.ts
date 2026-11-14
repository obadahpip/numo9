/**
 * Client for the product catalogue API (U-01-T09…T11, docs/architecture/feature-keys.md):
 * `/api/v1/catalogue/…` (every signed-in user) and `/api/v1/platform/catalogue/…`
 * (platform.catalogue.view). Every call resolves (never throws on an HTTP error).
 */
import { apiRequest, type ApiResult, type Numo9Error } from "@/auth/client";

export const CATALOGUE_API = "/api/v1/catalogue";
export const PLATFORM_CATALOGUE_API = "/api/v1/platform/catalogue";

export type ProductKind = "main" | "free_set" | "companion";
export type ProductStatus = "active" | "planned" | "retired";
export type FeatureAction = "read" | "write" | "approve";

export interface Feature {
  key: string;
  description: string;
  description_i18n_key: string;
  area: string;
  action: FeatureAction;
  is_read_only: boolean;
}

export interface Product {
  code: string;
  name: string;
  name_i18n_key: string;
  kind: ProductKind;
  kind_label: string;
  status: ProductStatus;
  status_label: string;
  billable: boolean;
  sort: number;
  feature_count: number;
}

export interface ProductDetail extends Product {
  features: Feature[];
}

export interface PackageColumn {
  code: string;
  name: string;
  products: string[];
}

export interface MatrixRow extends Feature {
  product: string;
  product_name: string;
  packages: string[];
}

export interface FeatureMatrix {
  products: Product[];
  packages: PackageColumn[];
  features: MatrixRow[];
}

export type CatalogueError = Numo9Error;

export const isCatalogueError = (body: unknown): body is CatalogueError =>
  typeof body === "object" &&
  body !== null &&
  "code" in body &&
  !("products" in body) &&
  !("features" in body);

export function listConsoleProducts(): Promise<
  ApiResult<{ products: ProductDetail[] } | CatalogueError>
> {
  return apiRequest(`${PLATFORM_CATALOGUE_API}/products`);
}

export function getFeatureMatrix(): Promise<ApiResult<FeatureMatrix | CatalogueError>> {
  return apiRequest(`${CATALOGUE_API}/feature-matrix`);
}

export function matrixExportUrl(kind: "csv" | "xlsx"): string {
  return `${PLATFORM_CATALOGUE_API}/feature-matrix/export/${kind}`;
}

export interface OrganisationMatrix extends FeatureMatrix {
  /** Code of the organisation's package; null before U-03/U-04 give it a subscription. */
  current_package: string | null;
}

export function getOrganisationMatrix(
  org: string,
): Promise<ApiResult<OrganisationMatrix | CatalogueError>> {
  return apiRequest(`/api/v1/o/${encodeURIComponent(org)}/package-features`);
}
