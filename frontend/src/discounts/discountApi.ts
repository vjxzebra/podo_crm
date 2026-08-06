import type { components } from "../api/schema";
import { sessionAwareFetch } from "../api/client";
import { csrfHeaders } from "../auth/AuthContext";

export interface Discount {
  readonly id: string;
  readonly name: string;
  readonly percent: number;
  readonly is_active: boolean;
  readonly version: number;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface DiscountListResponse {
  readonly discounts: readonly Discount[];
}

export interface LoyaltyPolicy {
  readonly key: "default";
  readonly is_active: boolean;
  readonly every_n: number;
  readonly discount: Discount | null;
  readonly version: number;
  readonly started_at: string | null;
  readonly updated_at: string;
}

export interface VisitPricingProjection {
  readonly gross_minor: number;
  readonly discount_id: string | null;
  readonly discount_name: string;
  readonly discount_percent: number | null;
  readonly discount_source: "" | "LOYALTY" | "PODOLOGIST" | "RECEPTION";
  readonly discount_amount_minor: number;
  readonly net_minor: number;
  readonly version: number;
  readonly state: "OPEN" | "SETTLED";
}

export interface DiscountCreateInput {
  readonly name: string;
  readonly percent: number;
  readonly is_active: boolean;
}

export interface DiscountUpdateInput {
  readonly name?: string;
  readonly percent?: number;
  readonly is_active?: boolean;
  readonly version: number;
}

export interface LoyaltyPolicyUpdateInput {
  readonly is_active: boolean;
  readonly every_n: number;
  readonly discount_id: string | null;
  readonly version: number;
}

export type DiscountStatus = "active" | "inactive" | "all";
export type DiscountApiError = components["schemas"]["ErrorEnvelope"];
export type DiscountApiResult<T> =
  | { readonly ok: true; readonly data: T; readonly status: number }
  | { readonly ok: false; readonly error: DiscountApiError; readonly status: number };

type Validator<T> = (value: unknown) => value is T;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isDiscount(value: unknown): value is Discount {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.name === "string"
    && typeof value.percent === "number"
    && typeof value.is_active === "boolean"
    && typeof value.version === "number"
    && typeof value.created_at === "string"
    && typeof value.updated_at === "string";
}

function isDiscountList(value: unknown): value is DiscountListResponse {
  return isRecord(value)
    && Array.isArray(value.discounts)
    && value.discounts.every(isDiscount);
}

function isLoyaltyPolicy(value: unknown): value is LoyaltyPolicy {
  return isRecord(value)
    && value.key === "default"
    && typeof value.is_active === "boolean"
    && typeof value.every_n === "number"
    && (value.discount === null || isDiscount(value.discount))
    && typeof value.version === "number"
    && (value.started_at === null || typeof value.started_at === "string")
    && typeof value.updated_at === "string";
}

function apiError(payload: unknown, fallback: string): DiscountApiError {
  if (isRecord(payload)) {
    return {
      code: typeof payload.code === "string" ? payload.code : "api_error",
      correlation_id: typeof payload.correlation_id === "string" ? payload.correlation_id : "",
      fields: isRecord(payload.fields)
        ? Object.fromEntries(Object.entries(payload.fields).filter((entry): entry is [string, string[]] => (
            Array.isArray(entry[1]) && entry[1].every((item) => typeof item === "string")
          )))
        : {},
      message: typeof payload.message === "string" ? payload.message : fallback,
    };
  }
  return { code: "api_error", correlation_id: "", fields: {}, message: fallback };
}

async function requestJson<T>(
  path: string,
  validator: Validator<T>,
  init: Readonly<{ method?: "GET" | "POST" | "PATCH"; body?: unknown; signal?: AbortSignal }> = {},
): Promise<DiscountApiResult<T>> {
  const headers = new Headers(csrfHeaders());
  headers.set("Accept", "application/json");
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  const request = new Request(new URL(path, window.location.origin), {
    method: init.method ?? "GET",
    headers,
    ...(init.body === undefined ? {} : { body: JSON.stringify(init.body) }),
    ...(init.signal === undefined ? {} : { signal: init.signal }),
  });
  const response = await sessionAwareFetch(request);
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    return {
      ok: false,
      error: apiError(payload, "Не вдалося виконати запит до каталогу знижок."),
      status: response.status,
    };
  }
  if (!validator(payload)) {
    return {
      ok: false,
      error: apiError(null, "Сервер повернув некоректні дані каталогу знижок."),
      status: response.status,
    };
  }
  return { ok: true, data: payload, status: response.status };
}

export function listDiscounts(
  status: DiscountStatus = "active",
  signal?: AbortSignal,
): Promise<DiscountApiResult<DiscountListResponse>> {
  const url = new URL("/api/v1/discounts", window.location.origin);
  url.searchParams.set("status", status);
  return requestJson(url.pathname + url.search, isDiscountList, {
    ...(signal === undefined ? {} : { signal }),
  });
}

export function createDiscount(
  input: DiscountCreateInput,
): Promise<DiscountApiResult<Discount>> {
  return requestJson("/api/v1/discounts", isDiscount, { method: "POST", body: input });
}

export function updateDiscount(
  discountId: string,
  input: DiscountUpdateInput,
): Promise<DiscountApiResult<Discount>> {
  return requestJson(`/api/v1/discounts/${encodeURIComponent(discountId)}`, isDiscount, {
    method: "PATCH",
    body: input,
  });
}

export function getLoyaltyPolicy(
  signal?: AbortSignal,
): Promise<DiscountApiResult<LoyaltyPolicy>> {
  return requestJson("/api/v1/loyalty-policy", isLoyaltyPolicy, {
    ...(signal === undefined ? {} : { signal }),
  });
}

export function updateLoyaltyPolicy(
  input: LoyaltyPolicyUpdateInput,
): Promise<DiscountApiResult<LoyaltyPolicy>> {
  return requestJson("/api/v1/loyalty-policy", isLoyaltyPolicy, {
    method: "PATCH",
    body: input,
  });
}
