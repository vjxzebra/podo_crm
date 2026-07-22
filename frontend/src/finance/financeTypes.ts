import type { components } from "../api/schema";

export type PaymentMethod = components["schemas"]["PaymentMethodEnum"];
export type FinanceOperation = components["schemas"]["FinanceOperation"];
export type FinancePaymentOperation = components["schemas"]["FinancePaymentOperation"];
export type FinanceRefundOperation = components["schemas"]["FinanceRefundOperation"];
export type FinanceCashAdjustmentOperation = components["schemas"]["FinanceCashAdjustmentOperation"];
export type RefundCreateRequest = components["schemas"]["RefundCreateRequest"];
export type RefundCreateResponse = components["schemas"]["RefundCreateResponse"];
export type CashMovementCreateRequest = components["schemas"]["CashMovementCreateRequest"];
export type CashMovementCreateResponse = components["schemas"]["CashMovementCreateResponse"];

export type OperationType = FinanceOperation["type"];
export type OperationStatus = FinanceOperation["status"];
export type CashMovementType = components["schemas"]["CashMovementTypeEnum"];

export function isPaymentOperation(operation: FinanceOperation): operation is FinancePaymentOperation {
  return operation.type === "PAYMENT";
}

export function isRefundOperation(operation: FinanceOperation): operation is FinanceRefundOperation {
  return operation.type === "REFUND";
}

export function isCashAdjustmentOperation(operation: FinanceOperation): operation is FinanceCashAdjustmentOperation {
  return operation.type === "DEPOSIT" || operation.type === "WITHDRAWAL";
}
