import { apiClient } from "../api/client";
import type { components } from "../api/schema";

export type OverviewResponse = components["schemas"]["OverviewResponse"];
export type OverviewAppointment = components["schemas"]["OverviewAppointment"];
export type OverviewMetric = components["schemas"]["OverviewMetric"];
export type AnalyticsResponse = components["schemas"]["AnalyticsResponse"];
export type AnalyticsKpi = components["schemas"]["AnalyticsKpi"];
export type ApiError = components["schemas"]["ErrorEnvelope"];

export type AnalyticsApiResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly error: ApiError; readonly status: number };

export async function getOverview(
  date: string,
  signal?: AbortSignal,
): Promise<AnalyticsApiResult<OverviewResponse>> {
  const { data, error, response } = await apiClient.GET("/api/v1/overview", {
    params: { query: { date } },
    ...(signal === undefined ? {} : { signal }),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}

export interface AnalyticsQuery {
  readonly dateFrom: string;
  readonly dateTo: string;
  readonly specialistId?: number;
  readonly serviceId?: string;
}

export async function getAnalytics(
  query: AnalyticsQuery,
  signal?: AbortSignal,
): Promise<AnalyticsApiResult<AnalyticsResponse>> {
  const { data, error, response } = await apiClient.GET("/api/v1/analytics", {
    params: {
      query: {
        from: query.dateFrom,
        to: query.dateTo,
        ...(query.specialistId === undefined ? {} : { specialist_id: query.specialistId }),
        ...(query.serviceId === undefined ? {} : { service_id: query.serviceId }),
      },
    },
    ...(signal === undefined ? {} : { signal }),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}
