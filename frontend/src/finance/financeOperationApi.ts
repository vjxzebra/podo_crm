import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import type { FinancePaymentOperation } from "./financeTypes";

type FinanceApiError = components["schemas"]["ErrorEnvelope"];

export type FinanceOperationDetailResult =
  | { readonly ok: true; readonly data: FinancePaymentOperation }
  | { readonly ok: false; readonly error: FinanceApiError; readonly status: number };

export async function getFinancePaymentOperation(
  operationId: string,
  signal: AbortSignal,
): Promise<FinanceOperationDetailResult> {
  const { data, error, response } = await apiClient.GET(
    "/api/v1/finance/operations/{operation_type}/{operation_id}",
    {
      params: { path: { operation_type: "PAYMENT", operation_id: operationId } },
      signal,
    },
  );
  return data === undefined
    ? {
        ok: false,
        error,
        status: response.status,
      }
    : { ok: true, data };
}
