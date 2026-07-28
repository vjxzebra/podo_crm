import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { csrfHeaders } from "../auth/AuthContext";

export type BookingRequest = components["schemas"]["BookingRequest"];
export type BookingRequestListResponse = components["schemas"]["BookingRequestListResponse"];
export type BookingRequestCounts = components["schemas"]["BookingRequestCounts"];
export type BookingRequestStatus = "ALL" | "NEW" | "PROCESSED";
export type BookingRequestSource = "ALL" | "INSTAGRAM" | "FACEBOOK" | "WEBSITE";

type BookingRequestApiError = components["schemas"]["ErrorEnvelope"];
export type BookingRequestApiResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly error: BookingRequestApiError; readonly status: number };

export interface BookingRequestListQuery {
  readonly status: BookingRequestStatus;
  readonly source: BookingRequestSource;
  readonly search?: string;
}

export async function listBookingRequests(
  query: BookingRequestListQuery,
  cursor?: string,
  signal?: AbortSignal,
): Promise<BookingRequestApiResult<BookingRequestListResponse>> {
  const { data, error, response } = await apiClient.GET("/api/v1/booking-requests", {
    params: {
      query: {
        status: query.status,
        source: query.source,
        ...(query.search === undefined ? {} : { search: query.search }),
        ...(cursor === undefined ? {} : { cursor }),
      },
    },
    ...(signal === undefined ? {} : { signal }),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}
export async function getBookingRequest(
  bookingRequestId: string,
  signal?: AbortSignal,
): Promise<BookingRequestApiResult<BookingRequest>> {
  const { data, error, response } = await apiClient.GET(
    "/api/v1/booking-requests/{booking_request_id}",
    {
      params: { path: { booking_request_id: bookingRequestId } },
      ...(signal === undefined ? {} : { signal }),
    },
  );
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}

export async function processBookingRequest(
  bookingRequestId: string,
  version: number,
): Promise<BookingRequestApiResult<BookingRequest>> {
  const { data, error, response } = await apiClient.POST(
    "/api/v1/booking-requests/{booking_request_id}/process",
    {
      params: { path: { booking_request_id: bookingRequestId } },
      body: { version },
      headers: csrfHeaders(),
    },
  );
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}
