import { apiClient } from "../api/client";
import type { components, operations } from "../api/schema";

export type AuditEventListItem = components["schemas"]["AuditEventListItem"];
export type AuditEventDetail = components["schemas"]["AuditEventDetail"];
export type AuditEventListResponse = components["schemas"]["AuditEventListResponse"];
export type AuditActorOption = components["schemas"]["TeamUser"];
export type AuditSection = NonNullable<NonNullable<
  operations["audit_event_list"]["parameters"]["query"]
>["section"]>;
export type AuditExportQuery = NonNullable<
  operations["audit_event_export"]["parameters"]["query"]
>;

export interface AuditListQuery {
  readonly search?: string;
  readonly actor_id?: number;
  readonly section?: AuditSection;
  readonly date_from?: string;
  readonly date_to?: string;
}

export function auditExportUrl(query: AuditListQuery): string {
  const url = new URL("/api/v1/audit-events/export", window.location.origin);
  const exportQuery: AuditExportQuery = {
    ...(query.search === undefined ? {} : { search: query.search }),
    ...(query.actor_id === undefined ? {} : { actor_id: query.actor_id }),
    ...(query.section === undefined ? {} : { section: query.section }),
    ...(query.date_from === undefined ? {} : { date_from: query.date_from }),
    ...(query.date_to === undefined ? {} : { date_to: query.date_to }),
  };
  for (const [name, value] of Object.entries(exportQuery)) {
    url.searchParams.set(name, String(value));
  }
  return url.toString();
}

type ApiError = components["schemas"]["ErrorEnvelope"];
export type AuditApiResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly error: ApiError; readonly status: number };

export async function listAuditEvents(
  query: AuditListQuery,
  cursor?: string,
  signal?: AbortSignal,
): Promise<AuditApiResult<AuditEventListResponse>> {
  const { data, error, response } = await apiClient.GET("/api/v1/audit-events", {
    params: {
      query: {
        ...query,
        ...(cursor === undefined ? {} : { cursor }),
      },
    },
    ...(signal === undefined ? {} : { signal }),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}

export async function getAuditEvent(
  eventId: string,
  signal?: AbortSignal,
): Promise<AuditApiResult<AuditEventDetail>> {
  const { data, error, response } = await apiClient.GET("/api/v1/audit-events/{event_id}", {
    params: { path: { event_id: eventId } },
    ...(signal === undefined ? {} : { signal }),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}

export async function listAuditActors(
  signal?: AbortSignal,
): Promise<AuditApiResult<readonly AuditActorOption[]>> {
  const { data, error, response } = await apiClient.GET("/api/v1/users", {
    params: { query: { status: "all" } },
    ...(signal === undefined ? {} : { signal }),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data: data.users };
}
