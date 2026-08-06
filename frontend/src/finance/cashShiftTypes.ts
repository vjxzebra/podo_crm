import type { components, operations } from "../api/schema";

export type CashShiftStatus = components["schemas"]["CashShiftStatusEnum"];
export type CashLedgerKind = components["schemas"]["CashLedgerEntryKindEnum"];
export type CashPaymentMethod = components["schemas"]["PaymentMethodEnum"];
export type CashShiftEmployeeSnapshot = components["schemas"]["CashShiftEmployee"];
export type CashShiftTotals = components["schemas"]["CashShiftTotals"];
export type CashLedgerEntrySnapshot = components["schemas"]["CashLedgerEntry"];
export type CashShiftReconciliation = components["schemas"]["CashShiftReconciliation"];
export type CashShiftOpeningBasis = "LEGACY" | "INITIAL" | "CARRY_FORWARD";
export interface CashShiftOpeningSource {
  readonly id: string;
  readonly public_number: string;
}
export interface CashShiftPermissions {
  readonly can_mutate: boolean;
  readonly can_close: boolean;
}
export interface CashShiftOpeningProjection {
  readonly drawer_key: "main";
  readonly opening_cash_minor: number;
  readonly opening_basis: CashShiftOpeningBasis;
  readonly opening_source_shift: CashShiftOpeningSource | null;
  readonly permissions: CashShiftPermissions;
}
export type CashShiftSummary = components["schemas"]["CashShiftSummary"] & CashShiftOpeningProjection;
export type CashShiftProjection = components["schemas"]["CashShiftProjection"] & CashShiftOpeningProjection;
export type CashShiftClosePreview = Omit<components["schemas"]["CashShiftClosePreviewResponse"], "shift"> & {
  readonly shift: CashShiftProjection;
};
export type CashShiftCloseRequest = components["schemas"]["CashShiftCloseRequest"];
export type CashShiftCloseResponse = Omit<components["schemas"]["CashShiftCloseResponse"], "shift"> & {
  readonly shift: CashShiftProjection;
};
export type CashShiftListResponse = Omit<components["schemas"]["CashShiftListResponse"], "shifts"> & {
  readonly shifts: readonly CashShiftSummary[];
};
export type CashShiftApiError = components["schemas"]["ErrorEnvelope"];
export type CashShiftListQuery = NonNullable<operations["cash_shift_list"]["parameters"]["query"]>;

export type CashShiftApiResult<T> =
  | { readonly ok: true; readonly data: T; readonly status: number }
  | { readonly ok: false; readonly error: CashShiftApiError; readonly status: number };
