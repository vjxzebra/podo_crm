import { apiClient } from "../api/client";
import { csrfHeaders } from "../auth/AuthContext";
import type {
  CashShiftApiResult,
  CashShiftClosePreview,
  CashShiftCloseRequest,
  CashShiftCloseResponse,
  CashShiftListQuery,
  CashShiftListResponse,
  CashShiftProjection,
} from "./cashShiftTypes";

export async function getCashShiftClosePreview(
  shiftId: string,
): Promise<CashShiftApiResult<CashShiftClosePreview>> {
  const { data, error, response } = await apiClient.GET("/api/v1/cash-shifts/{shift_id}/close-preview", {
    params: { path: { shift_id: shiftId } },
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data, status: response.status };
}

export async function closeCashShift(
  shiftId: string,
  body: CashShiftCloseRequest,
  idempotencyKey: string,
): Promise<CashShiftApiResult<CashShiftCloseResponse>> {
  const { data, error, response } = await apiClient.POST("/api/v1/cash-shifts/{shift_id}/close", {
    body,
    headers: csrfHeaders(),
    params: {
      path: { shift_id: shiftId },
      header: { "Idempotency-Key": idempotencyKey },
    },
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data, status: response.status };
}

export async function listCashShifts(
  query: CashShiftListQuery,
): Promise<CashShiftApiResult<CashShiftListResponse>> {
  const { data, error, response } = await apiClient.GET("/api/v1/cash-shifts", {
    params: { query },
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data, status: response.status };
}

export async function getCashShift(
  shiftId: string,
): Promise<CashShiftApiResult<CashShiftProjection>> {
  const { data, error, response } = await apiClient.GET("/api/v1/cash-shifts/{shift_id}", {
    params: { path: { shift_id: shiftId } },
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data, status: response.status };
}
