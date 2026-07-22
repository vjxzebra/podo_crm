import type { components, operations } from "../api/schema";

export type CashShiftStatus = components["schemas"]["CashShiftStatusEnum"];
export type CashLedgerKind = components["schemas"]["CashLedgerEntryKindEnum"];
export type CashPaymentMethod = components["schemas"]["PaymentMethodEnum"];
export type CashShiftEmployeeSnapshot = components["schemas"]["CashShiftEmployee"];
export type CashShiftTotals = components["schemas"]["CashShiftTotals"];
export type CashLedgerEntrySnapshot = components["schemas"]["CashLedgerEntry"];
export type CashShiftReconciliation = components["schemas"]["CashShiftReconciliation"];
export type CashShiftSummary = components["schemas"]["CashShiftSummary"];
export type CashShiftProjection = components["schemas"]["CashShiftProjection"];
export type CashShiftClosePreview = components["schemas"]["CashShiftClosePreviewResponse"];
export type CashShiftCloseRequest = components["schemas"]["CashShiftCloseRequest"];
export type CashShiftCloseResponse = components["schemas"]["CashShiftCloseResponse"];
export type CashShiftListResponse = components["schemas"]["CashShiftListResponse"];
export type CashShiftApiError = components["schemas"]["ErrorEnvelope"];
export type CashShiftListQuery = NonNullable<operations["cash_shift_list"]["parameters"]["query"]>;

export type CashShiftApiResult<T> =
  | { readonly ok: true; readonly data: T; readonly status: number }
  | { readonly ok: false; readonly error: CashShiftApiError; readonly status: number };
