import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type SyntheticEvent,
} from "react";
import { useSearchParams } from "react-router";

import { apiClient, sessionAwareFetch } from "../api/client";
import { attachmentFilename, downloadBlob, responseErrorMessage } from "../api/download";
import type { components, operations } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders, useAuth } from "../auth/AuthContext";
import {
  type Discount,
  listDiscounts,
  type VisitPricingProjection,
} from "../discounts/discountApi";
import { CashMovementDialog } from "./CashMovementDialog";
import { useFinanceDialogLifecycle } from "./dialogLifecycle";
import { getFinancePaymentOperation } from "./financeOperationApi";
import {
  dateTimeFormatter,
  methodLabels,
  money,
  shortDateTimeFormatter,
} from "./financeFormat";
import {
  type CashMovementType,
  type FinanceOperation,
  type FinancePaymentOperation,
  type FinanceRefundOperation,
  isCashAdjustmentOperation,
  isPaymentOperation,
  isRefundOperation,
  type OperationStatus,
  type OperationType,
  type PaymentMethod,
} from "./financeTypes";
import { PaymentReceiptActions, PaymentReceiptDialog } from "./PaymentReceipt";
import { RefundDialog } from "./RefundDialog";

type GeneratedOperationQuery = NonNullable<operations["finance_operation_list"]["parameters"]["query"]>;
type GeneratedOperationExportQuery = NonNullable<operations["finance_operation_export"]["parameters"]["query"]>;
type OperationQuery = Omit<GeneratedOperationQuery, "type" | "status"> & {
  readonly type?: OperationType;
  readonly status?: OperationStatus;
  readonly amount_minor?: number;
  readonly refundable_only?: boolean;
};
type PaymentCreateRequest = components["schemas"]["PaymentCreateRequest"];
type DiscountAction = PaymentCreateRequest["discount_action"];
type PricedFinancePaymentOperation = FinancePaymentOperation & {
  readonly pricing: VisitPricingProjection;
};
type TypeFilter = "all" | OperationType;
type StatusFilter = "all" | OperationStatus;
type MethodFilter = "all" | PaymentMethod;

export type FinanceCashActionState = "loading" | "error" | "closed" | "foreign" | "ready";

function financeOperationsExportUrl(query: OperationQuery): string {
  const url = new URL("/api/v1/finance/operations/export", window.location.origin);
  const exportQuery: GeneratedOperationExportQuery = {
    ...(query.search === undefined ? {} : { search: query.search }),
    ...(query.type === undefined ? {} : { type: query.type }),
    ...(query.status === undefined ? {} : { status: query.status }),
    ...(query.payment_method === undefined ? {} : { payment_method: query.payment_method }),
    ...(query.date_from === undefined ? {} : { date_from: query.date_from }),
    ...(query.date_to === undefined ? {} : { date_to: query.date_to }),
  };
  for (const [name, value] of Object.entries(exportQuery)) {
    url.searchParams.set(name, value);
  }
  return url.toString();
}

const statusLabels: Readonly<Record<OperationStatus, string>> = {
  OPEN: "Очікує оплати",
  PAID: "Оплачено",
  REFUNDED: "Повернено",
  POSTED: "Проведено",
};

const typeLabels: Readonly<Record<OperationType, string>> = {
  PAYMENT: "Оплата",
  REFUND: "Повернення",
  DEPOSIT: "Внесення",
  WITHDRAWAL: "Вилучення",
};

const discountSourceLabels: Readonly<Record<VisitPricingProjection["discount_source"], string>> = {
  "": "Без знижки",
  LOYALTY: "Програма лояльності",
  PODOLOGIST: "Подолог",
  RECEPTION: "Рецепція",
};

const paymentConflictCodes = new Set([
  "cash_shift_required",
  "discount_unavailable",
  "pricing_missing",
  "pricing_settled",
  "pricing_version_conflict",
  "receivable_already_paid",
  "receivable_already_refunded",
  "visit_not_payable",
]);

function calculateDiscountMinor(grossMinor: number, percent: number): number {
  const wholeHundreds = Math.floor(grossMinor / 100);
  const remainder = grossMinor % 100;
  return (wholeHundreds * percent) + Math.floor((remainder * percent) / 100);
}

function isZeroSettlement(operation: FinanceOperation): boolean {
  return isPaymentOperation(operation)
    && operation.status === "PAID"
    && operation.amount_minor === 0
    && operation.payment === null;
}

function isVisitPricingProjection(value: unknown): value is VisitPricingProjection {
  if (typeof value !== "object" || value === null) return false;
  const pricing = value as Partial<VisitPricingProjection>;
  return typeof pricing.gross_minor === "number"
    && (typeof pricing.discount_id === "string" || pricing.discount_id === null)
    && typeof pricing.discount_name === "string"
    && (typeof pricing.discount_percent === "number" || pricing.discount_percent === null)
    && ["", "LOYALTY", "PODOLOGIST", "RECEPTION"].includes(pricing.discount_source ?? "invalid")
    && typeof pricing.discount_amount_minor === "number"
    && typeof pricing.net_minor === "number"
    && typeof pricing.version === "number"
    && (pricing.state === "OPEN" || pricing.state === "SETTLED");
}

function isPricedPaymentOperation(operation: FinanceOperation): operation is PricedFinancePaymentOperation {
  return isPaymentOperation(operation)
    && isVisitPricingProjection(operation.pricing);
}

function isPayableOperation(operation: FinanceOperation): operation is PricedFinancePaymentOperation {
  return isPricedPaymentOperation(operation)
    && operation.status === "OPEN"
    && operation.amount_minor > 0
    && operation.pricing.state === "OPEN";
}

function isRefundableOperation(operation: FinanceOperation): operation is FinancePaymentOperation {
  return isPaymentOperation(operation)
    && operation.status === "PAID"
    && operation.amount_minor > 0
    && operation.payment !== null
    && operation.refund === null;
}

function operationMethod(operation: FinanceOperation): string {
  if (isZeroSettlement(operation)) return "Без оплати";
  if (isRefundOperation(operation)) return methodLabels[operation.original_payment.payment_method];
  if (isCashAdjustmentOperation(operation)) return "Не застосовується";
  return operation.payment === null ? "Не визначено" : methodLabels[operation.payment.payment_method];
}

function operationStatusLabel(operation: FinanceOperation): string {
  return isZeroSettlement(operation) ? "Без оплати" : statusLabels[operation.status];
}

function operationActorLabel(operation: FinanceOperation): string {
  if (isRefundOperation(operation)) return operation.refund.actor.name;
  if (isCashAdjustmentOperation(operation)) return operation.cash_adjustment.actor.name;
  if (operation.payment !== null) return operation.payment.actor.name;
  return isZeroSettlement(operation) ? "Закрито без оплати" : "Ще не проведено";
}

function operationNumber(operation: FinanceOperation): string {
  if (isRefundOperation(operation)) return operation.refund.public_number;
  if (isCashAdjustmentOperation(operation)) return operation.cash_adjustment.public_number;
  return operation.payment?.public_number ?? operation.visit.public_number;
}

function serviceSummary(operation: FinanceOperation): string {
  if (isCashAdjustmentOperation(operation)) return operation.cash_adjustment.reason;
  const first = operation.visit.services[0];
  if (first === undefined) return "Без послуг";
  const remaining = operation.visit.services.length - 1;
  return remaining === 0 ? first.name : `${first.name} · +${String(remaining)}`;
}

function operationPatientLabel(operation: FinanceOperation): string {
  return isCashAdjustmentOperation(operation) ? "Каса" : operation.patient.display_name;
}

function operationPatientMeta(operation: FinanceOperation): string {
  return isCashAdjustmentOperation(operation)
    ? operation.cash_adjustment.cash_shift.public_number
    : `${operation.patient.public_number} · ${operation.visit.public_number}`;
}

function operationShiftNumber(operation: FinanceOperation): string | null {
  if (isRefundOperation(operation)) return operation.refund.cash_shift.public_number;
  if (isCashAdjustmentOperation(operation)) return operation.cash_adjustment.cash_shift.public_number;
  return operation.payment?.cash_shift.public_number ?? null;
}

function operationAmount(operation: FinanceOperation): string {
  const formatted = money(operation.amount_minor);
  if (operation.type === "REFUND" || operation.type === "WITHDRAWAL") return `−${formatted}`;
  if (operation.type === "DEPOSIT" || operation.status !== "OPEN") return `+${formatted}`;
  return formatted;
}

function operationCountLabel(value: number): string {
  const lastTwo = value % 100;
  const last = value % 10;
  if (last === 1 && lastTwo !== 11) return "операція";
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return "операції";
  return "операцій";
}

function OperationDetailDialog({
  hasOpenShift,
  onClose,
  onPay,
  onRefund,
  operation,
}: {
  readonly hasOpenShift: boolean;
  readonly onClose: () => void;
  readonly onPay: (operation: PricedFinancePaymentOperation) => void;
  readonly onRefund: (operation: FinancePaymentOperation) => void;
  readonly operation: FinanceOperation;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useFinanceDialogLifecycle({ dialogRef, initialFocusRef: closeRef, onEscape: onClose });
  const zeroSettlement = isZeroSettlement(operation);
  const cashAdjustment = isCashAdjustmentOperation(operation) ? operation.cash_adjustment : null;
  const relatedPayment = isRefundOperation(operation)
    ? operation.original_payment
    : isPaymentOperation(operation) ? operation.payment : null;
  const relatedRefund = isRefundOperation(operation)
    ? operation.refund
    : isPaymentOperation(operation) ? operation.refund : null;
  const patient = isCashAdjustmentOperation(operation) ? null : operation.patient;
  const visit = isCashAdjustmentOperation(operation) ? null : operation.visit;

  return (
    <div
      className="modal-layer finance-operation-detail-layer"
      onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}
      role="presentation"
    >
      <section
        aria-labelledby="finance-operation-detail-title"
        aria-modal="true"
        className="modal-card finance-operation-detail"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Фінанси · Незмінний запис</p>
            <h2 id="finance-operation-detail-title">{operationNumber(operation)}</h2>
            <p>{dateTimeFormatter.format(new Date(operation.occurred_at))}</p>
          </div>
          <div className="finance-operation-detail__header-actions">
            <span className={`finance-operation-status finance-operation-status--${operation.status.toLocaleLowerCase()}`}>{operationStatusLabel(operation)}</span>
            <button aria-label="Закрити деталі фінансової операції" className="icon-button" onClick={onClose} ref={closeRef} type="button"><Icon name="close" /></button>
          </div>
        </header>

        <div className="finance-operation-detail__amount">
          <span>{operation.status === "OPEN" ? "До сплати" : "Сума операції"}</span>
          <strong>{operationAmount(operation)}</strong>
          <small>{zeroSettlement ? "Нульова сума · закрито без касової операції" : operationMethod(operation)}</small>
        </div>

        {patient === null ? (
          <section className="finance-operation-person finance-operation-person--cash" aria-label="Службова касова операція">
            <span className="finance-operation-cash-icon" aria-hidden="true"><Icon name="finance" /></span>
            <div><small>Касова операція</small><strong>{typeLabels[operation.type]}</strong><small>Не пов’язана з пацієнтом або способом оплати</small></div>
          </section>
        ) : (
          <section className="finance-operation-person" aria-label="Пацієнт і прийом">
            <span className="avatar" aria-hidden="true">{patient.display_name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toLocaleUpperCase("uk")}</span>
            <div><small>Пацієнт</small><strong>{patient.display_name}</strong><small>{patient.public_number} · {patient.phone}</small></div>
          </section>
        )}

        <dl className="finance-operation-facts">
          <div><dt>Тип</dt><dd>{typeLabels[operation.type]}</dd></div>
          <div><dt>Спосіб</dt><dd>{operationMethod(operation)}</dd></div>
          {visit === null ? null : <div><dt>Прийом</dt><dd>{visit.public_number}</dd></div>}
          {visit === null ? null : <div><dt>Завершено</dt><dd>{dateTimeFormatter.format(new Date(visit.completed_at))}</dd></div>}
          {visit === null ? null : <div><dt>Спеціаліст</dt><dd>{visit.specialist.name}</dd></div>}
          {isRefundOperation(operation) ? (
            <>
              <div><dt>Початкова оплата</dt><dd>{operation.original_payment.public_number}</dd></div>
              <div><dt>Оплату провів(-ла)</dt><dd>{operation.original_payment.actor.name}</dd></div>
              <div><dt>Зміна початкової оплати</dt><dd>{operation.original_payment.cash_shift.public_number}</dd></div>
              <div><dt>Повернення провів(-ла)</dt><dd>{operation.refund.actor.name}</dd></div>
              <div><dt>Зміна повернення</dt><dd>{operation.refund.cash_shift.public_number}</dd></div>
            </>
          ) : (
            <>
              {operationShiftNumber(operation) === null ? null : <div><dt>Касова зміна</dt><dd>{operationShiftNumber(operation)}</dd></div>}
              {relatedPayment === null && relatedRefund === null && cashAdjustment === null ? null : <div><dt>Провів(-ла)</dt><dd>{operationActorLabel(operation)}</dd></div>}
            </>
          )}
        </dl>

        {visit === null ? null : <section className="finance-operation-services" aria-labelledby="finance-operation-services-title">
          <header><h3 id="finance-operation-services-title">Послуги прийому</h3><span>{visit.services.length}</span></header>
          {visit.services.map((service) => (
            <article key={service.id}>
              <span><strong>{service.name}</strong><small>{service.code} · {service.quantity} × {money(service.unit_price_minor)}</small></span>
              <b>{money(service.line_total_minor)}</b>
            </article>
          ))}
        </section>}

        {isPaymentOperation(operation) && relatedRefund !== null ? <section className="finance-operation-link" aria-label="Пов’язане повернення"><Icon name="refresh" /><div><span>Повне повернення</span><strong>{relatedRefund.public_number} · {dateTimeFormatter.format(new Date(relatedRefund.posted_at))}</strong><small>{relatedRefund.reason}</small></div></section> : null}
        {cashAdjustment === null ? null : <div className="finance-operation-comment"><span>Причина</span><p>{cashAdjustment.reason}</p></div>}
        {isRefundOperation(operation) ? <div className="finance-operation-comment"><span>Причина повернення</span><p>{operation.refund.reason}</p></div> : null}
        {isPaymentOperation(operation) && operation.payment?.comment ? <div className="finance-operation-comment"><span>Коментар</span><p>{operation.payment.comment}</p></div> : null}
        {cashAdjustment?.comment ? <div className="finance-operation-comment"><span>Коментар</span><p>{cashAdjustment.comment}</p></div> : null}

        <footer className="modal-card__footer finance-operation-detail__footer">
          <span><Icon name="lock" />Фінансові записи не редагуються й не видаляються.</span>
          <div>
            <button className="button button--secondary" onClick={onClose} type="button">Готово</button>
            {relatedPayment === null ? null : (
              <PaymentReceiptActions
                paymentId={relatedPayment.id}
                publicNumber={relatedPayment.public_number}
              />
            )}
            {isPayableOperation(operation) && hasOpenShift ? <button className="button button--primary" onClick={() => { onPay(operation); }} type="button">Провести оплату</button> : null}
            {isRefundableOperation(operation) && hasOpenShift ? <button className="button button--danger" onClick={() => { onRefund(operation); }} type="button">Оформити повне повернення</button> : null}
          </div>
        </footer>
      </section>
    </div>
  );
}

interface PaymentDialogProps {
  readonly actionsEnabled: boolean;
  readonly initialOperation: PricedFinancePaymentOperation | null;
  readonly onClose: () => void;
  readonly onConflictRefresh: () => Promise<void>;
  readonly onSuccess: (operation: PricedFinancePaymentOperation, replayed: boolean) => Promise<void>;
}

function PaymentDialog({ actionsEnabled, initialOperation, onClose, onConflictRefresh, onSuccess }: PaymentDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const firstMethodRef = useRef<HTMLInputElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const continueEditingRef = useRef<HTMLButtonElement>(null);
  const idempotencyKey = useRef(crypto.randomUUID());
  const requestSequence = useRef(0);
  const submitInFlightRef = useRef(false);
  const [query, setQuery] = useState(initialOperation?.patient.display_name ?? "");
  const [results, setResults] = useState<readonly PricedFinancePaymentOperation[]>(initialOperation === null ? [] : [initialOperation]);
  const [selected, setSelected] = useState<PricedFinancePaymentOperation | null>(initialOperation);
  const [method, setMethod] = useState<PaymentMethod | "">("");
  const [comment, setComment] = useState("");
  const [discountAction, setDiscountAction] = useState<DiscountAction>("KEEP");
  const [discountId, setDiscountId] = useState("");
  const [discounts, setDiscounts] = useState<readonly Discount[]>([]);
  const [isDiscountsLoading, setIsDiscountsLoading] = useState(true);
  const [discountsError, setDiscountsError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(initialOperation === null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [conflictCode, setConflictCode] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRetryLocked, setIsRetryLocked] = useState(false);
  const [showDiscard, setShowDiscard] = useState(false);
  const [isResultsOpen, setIsResultsOpen] = useState(initialOperation === null);
  const [activeIndex, setActiveIndex] = useState(0);
  const selectedDiscount = useMemo(
    () => discounts.find((discount) => discount.id === discountId) ?? null,
    [discountId, discounts],
  );
  const dirty = selected !== initialOperation
    || method !== ""
    || comment !== ""
    || discountAction !== "KEEP"
    || discountId !== "";
  const controlsLocked = !actionsEnabled || isSubmitting || isRetryLocked || conflictCode !== null;
  const discountSelectionValid = discountAction === "KEEP" || selectedDiscount !== null;

  const requestClose = useCallback(() => {
    if (isSubmitting || isRetryLocked) return;
    if (showDiscard) {
      setShowDiscard(false);
      window.setTimeout(() => { (selected === null ? searchRef.current : firstMethodRef.current)?.focus(); }, 0);
      return;
    }
    if (dirty) {
      setShowDiscard(true);
      return;
    }
    onClose();
  }, [dirty, isRetryLocked, isSubmitting, onClose, selected, showDiscard]);

  useFinanceDialogLifecycle({
    dialogRef,
    initialFocusRef: initialOperation === null ? searchRef : firstMethodRef,
    onEscape: requestClose,
  });

  const loadDiscountCatalog = useCallback(async (signal?: AbortSignal) => {
    setIsDiscountsLoading(true);
    setDiscountsError(null);
    const result = await listDiscounts("active", signal).catch(() => null);
    if (signal?.aborted === true) return;
    setIsDiscountsLoading(false);
    if (result === null) {
      setDiscountsError("Немає зв’язку із сервером. Не вдалося завантажити активні знижки.");
      return;
    }
    if (!result.ok) {
      setDiscountsError(result.error.message);
      return;
    }
    setDiscounts(result.data.discounts.filter((discount) => discount.is_active));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadDiscountCatalog(controller.signal);
    return () => { controller.abort(); };
  }, [loadDiscountCatalog]);

  const searchOpenOperations = useCallback(async (search: string) => {
    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    setIsSearching(true);
    setSearchError(null);
    const response = await apiClient.GET("/api/v1/finance/operations", {
      params: {
        query: {
          type: "PAYMENT",
          status: "OPEN",
          ...(search.trim() === "" ? {} : { search: search.trim() }),
        },
      },
    }).catch(() => null);
    if (sequence !== requestSequence.current) return;
    setIsSearching(false);
    if (response === null) {
      setSearchError("Немає зв’язку із сервером. Не вдалося знайти неоплачені прийоми.");
      return;
    }
    if (response.data === undefined) {
      setSearchError(response.error.message);
      return;
    }
    setResults(response.data.operations.filter(isPayableOperation));
    setActiveIndex(0);
  }, []);

  useEffect(() => {
    if (selected !== null && query === selected.patient.display_name) return;
    const timeout = window.setTimeout(() => { void searchOpenOperations(query); }, 250);
    return () => { window.clearTimeout(timeout); };
  }, [query, searchOpenOperations, selected]);

  useEffect(() => {
    if (submitError !== null) window.setTimeout(() => { errorRef.current?.focus(); }, 0);
  }, [submitError]);

  useEffect(() => {
    if (showDiscard) window.setTimeout(() => { continueEditingRef.current?.focus(); }, 0);
  }, [showDiscard]);

  const selectOperation = (operation: PricedFinancePaymentOperation) => {
    setSelected(operation);
    setQuery(operation.patient.display_name);
    setResults([operation]);
    setDiscountAction("KEEP");
    setDiscountId("");
    setIsResultsOpen(false);
    setSubmitError(null);
    setConflictCode(null);
    window.setTimeout(() => { firstMethodRef.current?.focus(); }, 0);
  };

  const chooseAnotherOperation = () => {
    idempotencyKey.current = crypto.randomUUID();
    setSelected(null);
    setMethod("");
    setComment("");
    setDiscountAction("KEEP");
    setDiscountId("");
    setConflictCode(null);
    setSubmitError(null);
    setIsRetryLocked(false);
    setQuery("");
    setResults([]);
    setIsResultsOpen(true);
    window.setTimeout(() => { searchRef.current?.focus(); }, 0);
  };

  const onSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (!isResultsOpen && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      event.preventDefault();
      setIsResultsOpen(true);
      return;
    }
    if (!isResultsOpen || results.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (current - 1 + results.length) % results.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const operation = results[activeIndex];
      if (operation !== undefined) selectOperation(operation);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      setIsResultsOpen(false);
    }
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      submitInFlightRef.current
      || !actionsEnabled
      || selected === null
      || method === ""
      || conflictCode !== null
      || !discountSelectionValid
    ) return;
    submitInFlightRef.current = true;
    setIsSubmitting(true);
    setSubmitError(null);
    const body: PaymentCreateRequest = {
      visit_id: selected.visit.id,
      payment_method: method,
      pricing_version: selected.pricing.version,
      discount_action: discountAction,
      ...(discountAction === "SET" && selectedDiscount !== null
        ? { discount_id: selectedDiscount.id }
        : {}),
      comment: comment.trim(),
    };
    const response = await apiClient.POST("/api/v1/payments", {
      body,
      headers: csrfHeaders(),
      params: { header: { "Idempotency-Key": idempotencyKey.current } },
    }).catch(() => null);
    if (response === null) {
      submitInFlightRef.current = false;
      setIsSubmitting(false);
      setIsRetryLocked(true);
      setSubmitError("Немає зв’язку із сервером. Дані збережено у формі — повторіть із тим самим запитом.");
      return;
    }
    if (response.data !== undefined) {
      const operation = response.data.operation;
      if (!isPricedPaymentOperation(operation)) {
        submitInFlightRef.current = false;
        setIsSubmitting(false);
        setIsRetryLocked(false);
        setSubmitError("Сервер повернув оплату без актуального розрахунку. Оновіть журнал перед повторною спробою.");
        await onConflictRefresh();
        return;
      }
      await onSuccess(operation, response.data.replayed);
      return;
    }
    const problem = response.error;
    const code = problem.code;
    submitInFlightRef.current = false;
    setIsSubmitting(false);
    setIsRetryLocked(false);
    setSubmitError(problem.message);
    if (paymentConflictCodes.has(code)) {
      setConflictCode(code);
      await Promise.all([
        onConflictRefresh(),
        code === "discount_unavailable" ? loadDiscountCatalog() : Promise.resolve(),
      ]);
      return;
    }
    if (["idempotency_payload_mismatch", "idempotency_key_conflict"].includes(code)) {
      idempotencyKey.current = crypto.randomUUID();
    }
  };

  const previewDiscountAmount = selected === null
    ? 0
    : discountAction === "SET" && selectedDiscount !== null
      ? calculateDiscountMinor(selected.pricing.gross_minor, selectedDiscount.percent)
      : selected.pricing.discount_amount_minor;
  const previewNet = selected === null
    ? 0
    : selected.pricing.gross_minor - previewDiscountAmount;
  const previewDiscountName = discountAction === "SET" && selectedDiscount !== null
    ? selectedDiscount.name
    : selected?.pricing.discount_name ?? "";
  const previewDiscountPercent = discountAction === "SET" && selectedDiscount !== null
    ? selectedDiscount.percent
    : selected?.pricing.discount_percent ?? null;
  const previewDiscountSource = discountAction === "SET" && selectedDiscount !== null
    ? "RECEPTION"
    : selected?.pricing.discount_source ?? "";

  return (
    <div
      className="modal-layer finance-payment-layer"
      onMouseDown={(event) => { if (event.currentTarget === event.target) requestClose(); }}
      role="presentation"
    >
      <section
        aria-busy={isSubmitting}
        aria-labelledby="finance-payment-title"
        aria-modal="true"
        className="modal-card finance-payment-dialog"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        {showDiscard ? (
          <div className="finance-payment-discard">
            <span className="finance-payment-discard__icon"><Icon name="warning" /></span>
            <p className="eyebrow">Незбережена оплата</p>
            <h2 id="finance-payment-title">Відхилити введені дані?</h2>
            <p>Обраний прийом, спосіб оплати, знижка та коментар буде втрачено.</p>
            <div>
              <button className="button button--secondary" onClick={() => { setShowDiscard(false); window.setTimeout(() => { (selected === null ? searchRef.current : firstMethodRef.current)?.focus(); }, 0); }} ref={continueEditingRef} type="button">Продовжити заповнення</button>
              <button className="button button--primary" onClick={onClose} type="button">Відхилити дані</button>
            </div>
          </div>
        ) : (
          <form onSubmit={(event) => { void submit(event); }}>
            <header className="modal-card__header">
              <div><p className="eyebrow">Фінанси · Повна оплата</p><h2 id="finance-payment-title">Провести оплату прийому</h2><p>Можна залишити поточну знижку або замінити її активною з каталогу. Знижки не сумуються.</p></div>
              <button aria-label="Закрити форму оплати" className="icon-button" disabled={isSubmitting || isRetryLocked} onClick={requestClose} type="button"><Icon name="close" /></button>
            </header>

            <div className="finance-payment-search">
              <label htmlFor="finance-payment-search-input">Неоплачений прийом</label>
              <div className="input-with-icon">
                <Icon name="search" />
                <input
                  aria-activedescendant={isResultsOpen && results[activeIndex] !== undefined ? `finance-payment-option-${results[activeIndex].id}` : undefined}
                  aria-autocomplete="list"
                  aria-controls="finance-payment-results"
                  aria-expanded={isResultsOpen}
                  autoComplete="off"
                  disabled={controlsLocked}
                  id="finance-payment-search-input"
                  maxLength={255}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setSelected(null);
                    setDiscountAction("KEEP");
                    setDiscountId("");
                    setConflictCode(null);
                    setSubmitError(null);
                    setIsResultsOpen(true);
                  }}
                  onFocus={() => { setIsResultsOpen(true); }}
                  onKeyDown={onSearchKeyDown}
                  placeholder="Ім’я, телефон або № пацієнта"
                  ref={searchRef}
                  role="combobox"
                  value={query}
                />
              </div>
              {isResultsOpen ? (
                <div aria-label="Неоплачені завершені прийоми" className="finance-payment-results" id="finance-payment-results" role="listbox">
                  {isSearching ? <div className="finance-payment-results__state" role="status"><span className="spinner" />Шукаємо прийоми…</div> : null}
                  {!isSearching && searchError !== null ? <div className="finance-payment-results__state finance-payment-results__state--error" role="alert"><Icon name="warning" /><span>{searchError}</span><button className="text-action" onClick={() => { void searchOpenOperations(query); }} type="button">Повторити</button></div> : null}
                  {!isSearching && searchError === null && results.length === 0 ? <div className="finance-payment-results__state"><Icon name="empty" /><span>Неоплачених прийомів не знайдено.</span></div> : null}
                  {!isSearching && searchError === null ? results.map((operation, index) => (
                    <button
                      aria-selected={index === activeIndex}
                      className={index === activeIndex ? "finance-payment-option finance-payment-option--active" : "finance-payment-option"}
                      disabled={controlsLocked}
                      id={`finance-payment-option-${operation.id}`}
                      key={operation.id}
                      onClick={() => { selectOperation(operation); }}
                      onMouseEnter={() => { setActiveIndex(index); }}
                      role="option"
                      tabIndex={-1}
                      type="button"
                    >
                      <span className="avatar" aria-hidden="true">{operation.patient.display_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("")}</span>
                      <span><strong>{operation.patient.display_name}</strong><small>{operation.patient.public_number} · {operation.patient.phone}</small><small>{operation.visit.public_number} · {shortDateTimeFormatter.format(new Date(operation.visit.completed_at))}</small></span>
                      <b>{money(operation.amount_minor)}</b>
                    </button>
                  )) : null}
                </div>
              ) : null}
            </div>

            {selected === null ? <div className="finance-payment-placeholder"><Icon name="finance" /><p>Знайдіть пацієнта й оберіть завершений неоплачений прийом.</p></div> : (
              <>
                <section className="finance-payment-summary" aria-labelledby="finance-payment-summary-title">
                  <header><div><p className="eyebrow">До оплати</p><h3 id="finance-payment-summary-title">{selected.patient.display_name}</h3><p>{selected.visit.public_number} · {dateTimeFormatter.format(new Date(selected.visit.completed_at))} · {selected.visit.specialist.name}</p></div><strong>{money(previewNet)}</strong></header>
                  <div>
                    {selected.visit.services.map((service) => <article key={service.id}><span><strong>{service.name}</strong><small>{service.code} · {service.quantity} × {money(service.unit_price_minor)}</small></span><b>{money(service.line_total_minor)}</b></article>)}
                  </div>
                  <div aria-label="Розрахунок оплати" className="finance-payment-pricing-group" role="group">
                    <dl className="finance-payment-pricing">
                      <dt>Вартість послуг</dt><dd>{money(selected.pricing.gross_minor)}</dd>
                      <dt>Знижка</dt><dd>{previewDiscountPercent === null ? "Без знижки" : `${previewDiscountName} · ${String(previewDiscountPercent)}% · −${money(previewDiscountAmount)}`}</dd>
                      <dt>Джерело знижки</dt><dd>{discountSourceLabels[previewDiscountSource]}</dd>
                      <dt className="finance-payment-pricing__total">До сплати</dt><dd className="finance-payment-pricing__total">{money(previewNet)}</dd>
                      <dt className="finance-payment-pricing__version">Версія розрахунку</dt><dd className="finance-payment-pricing__version">№ {selected.pricing.version}</dd>
                    </dl>
                  </div>
                </section>

                <fieldset className="finance-payment-discounts">
                  <legend>Знижка при оплаті</legend>
                  <label>
                    <input checked={discountAction === "KEEP"} disabled={controlsLocked} name="payment-discount-action" onChange={() => { setDiscountAction("KEEP"); setDiscountId(""); setSubmitError(null); }} type="radio" value="KEEP" />
                    <span><strong>Залишити поточну</strong><small>{selected.pricing.discount_percent === null ? "Прийом без знижки" : `${selected.pricing.discount_name} · ${String(selected.pricing.discount_percent)}%`}</small></span>
                  </label>
                  <label>
                    <input checked={discountAction === "SET"} disabled={controlsLocked || isDiscountsLoading || discounts.length === 0} name="payment-discount-action" onChange={() => { setDiscountAction("SET"); setSubmitError(null); }} type="radio" value="SET" />
                    <span><strong>Замінити знижку</strong><small>Одна активна знижка від рецепції</small></span>
                  </label>
                  {discountAction === "SET" ? (
                    <label className="form-field finance-payment-discount-picker">
                      <span>Активна знижка</span>
                      <select disabled={controlsLocked || isDiscountsLoading} onChange={(event) => { setDiscountId(event.target.value); setSubmitError(null); }} required value={discountId}>
                        <option value="">Оберіть знижку</option>
                        {discounts.map((discount) => <option key={discount.id} value={discount.id}>{discount.name} · {discount.percent}%</option>)}
                      </select>
                    </label>
                  ) : null}
                  {isDiscountsLoading ? <p className="finance-payment-discounts__state" role="status"><span className="spinner" />Завантажуємо активні знижки…</p> : null}
                  {!isDiscountsLoading && discountsError !== null ? <p className="finance-payment-discounts__state finance-payment-discounts__state--error" role="alert"><Icon name="warning" /><span>{discountsError}</span><button className="text-action" disabled={controlsLocked} onClick={() => { void loadDiscountCatalog(); }} type="button">Повторити</button></p> : null}
                  {!isDiscountsLoading && discountsError === null && discounts.length === 0 ? <p className="finance-payment-discounts__state">Активних знижок немає — можна лише залишити поточний розрахунок.</p> : null}
                </fieldset>

                <fieldset className="finance-payment-methods">
                  <legend>Спосіб оплати</legend>
                  {(["CASH", "CARD", "TRANSFER"] as const).map((value, index) => (
                    <label key={value}><input checked={method === value} disabled={controlsLocked} name="payment-method" onChange={() => { setMethod(value); setSubmitError(null); }} ref={index === 0 ? firstMethodRef : undefined} type="radio" value={value} /><span><Icon name="finance" /><strong>{methodLabels[value]}</strong></span></label>
                  ))}
                </fieldset>

                <label className="form-field finance-payment-comment"><span>Коментар <small>Необов’язково</small></span><textarea disabled={controlsLocked} maxLength={2000} onChange={(event) => { setComment(event.target.value); }} placeholder="Додаткова інформація про оплату" rows={3} value={comment} /></label>
              </>
            )}

            {submitError === null ? null : <div className="form-message form-message--error finance-payment-error" ref={errorRef} role="alert" tabIndex={-1}><Icon name="warning" /><span>{submitError}</span>{conflictCode === null ? null : conflictCode === "cash_shift_required" ? <button className="text-action" onClick={onClose} type="button">Повернутися до каси</button> : <button className="text-action" onClick={chooseAnotherOperation} type="button">Обрати інший прийом</button>}</div>}

            <footer className="modal-card__footer finance-payment-footer">
              <button className="button button--secondary" disabled={isSubmitting || isRetryLocked} onClick={requestClose} type="button">Скасувати</button>
              <button className="button button--primary" disabled={!actionsEnabled || selected === null || method === "" || !discountSelectionValid || isSubmitting || conflictCode !== null} type="submit">{isSubmitting ? "Проводимо…" : isRetryLocked ? "Повторити той самий запит" : "Провести повну оплату"}</button>
            </footer>
          </form>
        )}
      </section>
    </div>
  );
}

interface FinanceOperationsProps {
  readonly availableCashMinor: number;
  readonly cashActionState: FinanceCashActionState;
  readonly onOperationSuccess: (message: string) => void;
  readonly refreshShift: () => Promise<unknown>;
}

export function FinanceOperations({ availableCashMinor, cashActionState, onOperationSuccess, refreshShift }: FinanceOperationsProps) {
  const { state: authState } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [type, setType] = useState<TypeFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [method, setMethod] = useState<MethodFilter>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [query, setQuery] = useState<OperationQuery>({});
  const [operations, setOperations] = useState<readonly FinanceOperation[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterError, setFilterError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const [detail, setDetail] = useState<FinanceOperation | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<{ readonly message: string; readonly correlationId: string } | null>(null);
  const [paymentInitial, setPaymentInitial] = useState<PricedFinancePaymentOperation | null | undefined>(undefined);
  const [receiptOperation, setReceiptOperation] = useState<FinancePaymentOperation | null>(null);
  const [refundInitial, setRefundInitial] = useState<FinancePaymentOperation | null | undefined>(undefined);
  const [cashMovementType, setCashMovementType] = useState<CashMovementType | null>(null);
  const [isRefreshingAfterMutation, setIsRefreshingAfterMutation] = useState(false);
  const detailTriggerRef = useRef<HTMLButtonElement | null>(null);
  const paymentTriggerRef = useRef<HTMLButtonElement | null>(null);
  const refundTriggerRef = useRef<HTMLButtonElement | null>(null);
  const cashMovementTriggerRef = useRef<HTMLButtonElement | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const listRequestSequence = useRef(0);
  const detailRequestSequence = useRef(0);

  const load = useCallback(async (currentQuery: OperationQuery, append = false) => {
    const sequence = listRequestSequence.current + 1;
    listRequestSequence.current = sequence;
    setIsLoading(true);
    setError(null);
    const response = await apiClient.GET("/api/v1/finance/operations", {
      params: { query: currentQuery },
    }).catch(() => null);
    if (sequence !== listRequestSequence.current) return;
    setIsLoading(false);
    if (response === null) {
      setError("Немає зв’язку із сервером. Не вдалося завантажити фінансові операції.");
      return;
    }
    if (response.data === undefined) {
      setError(response.error.message);
      return;
    }
    const data = response.data;
    setOperations((current) => append ? [...current, ...data.operations] : data.operations);
    setNextCursor(data.next_cursor);
  }, []);

  useEffect(() => {
    setExportError(null);
    setExportStatus(null);
    void load(query);
  }, [load, query]);

  const requestedOperation = searchParams.get("operation");
  const requestedPaymentId = requestedOperation?.match(/^PAYMENT:([0-9a-f-]{36})$/i)?.[1] ?? null;
  const loadRequestedOperation = useCallback(async (operationId: string) => {
    const sequence = detailRequestSequence.current + 1;
    detailRequestSequence.current = sequence;
    setIsDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    const controller = new AbortController();
    try {
      const result = await getFinancePaymentOperation(operationId, controller.signal);
      if (sequence !== detailRequestSequence.current) return;
      setIsDetailLoading(false);
      if (!result.ok) {
        setDetailError({
          message: result.status === 403 || result.status === 404
            ? "Фінансову операцію не знайдено або вона недоступна у межах вашої ролі."
            : result.error.message,
          correlationId: result.error.correlation_id,
        });
        return;
      }
      setDetail(result.data);
    } catch {
      if (sequence !== detailRequestSequence.current) return;
      setIsDetailLoading(false);
      setDetailError({ message: "Немає зв’язку із сервером. Не вдалося відкрити фінансову операцію.", correlationId: "" });
    }
  }, []);

  useEffect(() => {
    if (requestedOperation === null) return;
    if (requestedPaymentId === null) {
      setDetail(null);
      setIsDetailLoading(false);
      setDetailError({ message: "Посилання на фінансову операцію некоректне або більше не підтримується.", correlationId: "" });
      return;
    }
    void loadRequestedOperation(requestedPaymentId);
    return () => { detailRequestSequence.current += 1; };
  }, [loadRequestedOperation, requestedOperation, requestedPaymentId]);

  const draftFiltersActive = search !== "" || type !== "all" || status !== "all" || method !== "all" || dateFrom !== "" || dateTo !== "";
  const appliedFiltersActive = Object.keys(query).length > 0;
  const canResetFilters = draftFiltersActive || appliedFiltersActive;
  const openCount = useMemo(() => operations.filter(isPayableOperation).length, [operations]);
  const effectiveCashActionState = isRefreshingAfterMutation ? "loading" : cashActionState;
  const mutationActionsAvailable = effectiveCashActionState === "ready";
  const isAdmin = authState.status === "authenticated" && authState.session.user.role === "admin";
  const draftDateInvalid = dateFrom !== "" && dateTo !== "" && dateFrom > dateTo;
  const exportDisabled = isLoading
    || error !== null
    || filterError !== null
    || draftDateInvalid
    || isExporting;

  const applyFilters = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (dateFrom !== "" && dateTo !== "" && dateFrom > dateTo) {
      setFilterError("Дата «Від» не може бути пізнішою за дату «До».");
      return;
    }
    setFilterError(null);
    setQuery({
      ...(type === "all" ? {} : { type }),
      ...(status === "all" ? {} : { status }),
      ...(method === "all" ? {} : { payment_method: method }),
      ...(search.trim() === "" ? {} : { search: search.trim() }),
      ...(dateFrom === "" ? {} : { date_from: dateFrom }),
      ...(dateTo === "" ? {} : { date_to: dateTo }),
    });
  };

  const resetFilters = () => {
    setSearch("");
    setType("all");
    setStatus("all");
    setMethod("all");
    setDateFrom("");
    setDateTo("");
    setFilterError(null);
    setQuery({});
  };

  const exportOperations = async () => {
    if (!isAdmin || exportDisabled) return;
    setIsExporting(true);
    setExportError(null);
    setExportStatus(null);
    const response = await sessionAwareFetch(new Request(
      financeOperationsExportUrl(query),
      { headers: { Accept: "text/csv" } },
    )).catch(() => null);
    if (response === null) {
      setExportError("Немає зв’язку із сервером. Не вдалося експортувати фінансові операції.");
      setIsExporting(false);
      return;
    }
    if (!response.ok) {
      setExportError(await responseErrorMessage(
        response,
        "Не вдалося експортувати фінансові операції.",
      ));
      setIsExporting(false);
      return;
    }
    const blob = await response.blob();
    downloadBlob(
      blob,
      attachmentFilename(
        response.headers.get("Content-Disposition"),
        "finance-operations.csv",
      ),
    );
    setIsExporting(false);
    setExportStatus("Завантаження CSV фінансових операцій розпочато.");
  };

  const closeDetail = () => {
    detailRequestSequence.current += 1;
    setDetail(null);
    setDetailError(null);
    setIsDetailLoading(false);
    if (requestedOperation !== null) {
      const next = new URLSearchParams(searchParams);
      next.delete("operation");
      setSearchParams(next, { replace: true });
    }
    window.setTimeout(() => { detailTriggerRef.current?.focus(); }, 0);
  };

  const openPayment = (operation: PricedFinancePaymentOperation | null, trigger?: HTMLButtonElement) => {
    if (!mutationActionsAvailable) return;
    paymentTriggerRef.current = trigger ?? detailTriggerRef.current;
    setDetail(null);
    setDetailError(null);
    if (requestedOperation !== null) {
      const next = new URLSearchParams(searchParams);
      next.delete("operation");
      setSearchParams(next, { replace: true });
    }
    setPaymentInitial(operation);
  };

  const closePayment = () => {
    setPaymentInitial(undefined);
    window.setTimeout(() => { paymentTriggerRef.current?.focus(); }, 0);
  };

  const closeReceipt = () => {
    setReceiptOperation(null);
    window.setTimeout(() => { headingRef.current?.focus(); }, 0);
  };

  const openRefund = (operation: FinancePaymentOperation | null, trigger?: HTMLButtonElement) => {
    if (!mutationActionsAvailable) return;
    refundTriggerRef.current = trigger ?? detailTriggerRef.current;
    setDetail(null);
    setDetailError(null);
    if (requestedOperation !== null) {
      const next = new URLSearchParams(searchParams);
      next.delete("operation");
      setSearchParams(next, { replace: true });
    }
    setRefundInitial(operation);
  };

  const closeRefund = () => {
    setRefundInitial(undefined);
    window.setTimeout(() => { refundTriggerRef.current?.focus(); }, 0);
  };

  const openCashMovement = (movementType: CashMovementType, trigger: HTMLButtonElement) => {
    if (!mutationActionsAvailable) return;
    cashMovementTriggerRef.current = trigger;
    setCashMovementType(movementType);
  };

  const closeCashMovement = () => {
    setCashMovementType(null);
    window.setTimeout(() => { cashMovementTriggerRef.current?.focus(); }, 0);
  };

  const refreshAll = useCallback(async () => {
    await Promise.all([load(query), refreshShift()]);
  }, [load, query, refreshShift]);

  const paymentSucceeded = async (operation: PricedFinancePaymentOperation, replayed: boolean) => {
    setIsRefreshingAfterMutation(true);
    setPaymentInitial(undefined);
    await refreshAll();
    setIsRefreshingAfterMutation(false);
    onOperationSuccess(replayed
      ? `Оплату ${operationNumber(operation)} вже було проведено. Показуємо актуальні дані.`
      : `Оплату ${operationNumber(operation)} на ${money(operation.amount_minor)} проведено.`);
    setReceiptOperation(operation);
  };

  const refundSucceeded = async (operation: FinanceRefundOperation, replayed: boolean) => {
    setIsRefreshingAfterMutation(true);
    setRefundInitial(undefined);
    await refreshAll();
    setIsRefreshingAfterMutation(false);
    onOperationSuccess(replayed
      ? `Повернення ${operationNumber(operation)} вже було проведено. Показуємо актуальні дані.`
      : `Повне повернення ${operationNumber(operation)} на ${money(operation.amount_minor)} проведено.`);
    window.setTimeout(() => { headingRef.current?.focus(); }, 0);
  };

  const cashMovementSucceeded = async (operation: Extract<FinanceOperation, { type: "DEPOSIT" | "WITHDRAWAL" }>, replayed: boolean) => {
    setIsRefreshingAfterMutation(true);
    setCashMovementType(null);
    await refreshAll();
    setIsRefreshingAfterMutation(false);
    const label = operation.type === "DEPOSIT" ? "Внесення" : "Вилучення";
    onOperationSuccess(replayed
      ? `${label} ${operationNumber(operation)} вже було проведено. Показуємо актуальні дані.`
      : `${label} ${operationNumber(operation)} на ${money(operation.amount_minor)} проведено.`);
    window.setTimeout(() => { headingRef.current?.focus(); }, 0);
  };

  return (
    <>
      <section aria-busy={isLoading} className="panel finance-operations" aria-labelledby="finance-operations-title">
        <header className="finance-operations__header">
          <div><p className="eyebrow">Оплати · Повернення · Каса</p><h2 id="finance-operations-title" ref={headingRef} tabIndex={-1}>Фінансові операції</h2><p>Завершені прийоми та всі незмінні касові операції в одному журналі.</p></div>
          <div className="finance-operations__header-meta">
            <span>{operations.length} {operationCountLabel(operations.length)}{openCount > 0 ? ` · ${String(openCount)} очікує` : ""}</span>
            {isAdmin ? <button className="button button--secondary finance-operations__export" disabled={exportDisabled} onClick={() => { void exportOperations(); }} type="button">{isExporting ? "Готуємо CSV…" : "Експортувати CSV"}</button> : null}
            {mutationActionsAvailable ? <div className="finance-operation-actions"><button className="button button--primary" onClick={(event) => { openPayment(null, event.currentTarget); }} type="button"><Icon name="plus" />Провести оплату</button><button className="button button--secondary" onClick={(event) => { openRefund(null, event.currentTarget); }} type="button"><Icon name="refresh" />Повернення</button><button className="button button--secondary" onClick={(event) => { openCashMovement("DEPOSIT", event.currentTarget); }} type="button">+ Внесення</button><button className="button button--secondary" onClick={(event) => { openCashMovement("WITHDRAWAL", event.currentTarget); }} type="button">− Вилучення</button></div> : <span aria-label={effectiveCashActionState === "loading" ? "Оновлюємо касову зміну — операції тимчасово недоступні" : undefined} className="finance-operations__shift-note" role={effectiveCashActionState === "loading" ? "status" : undefined}><Icon name={effectiveCashActionState === "loading" ? "refresh" : "warning"} />{effectiveCashActionState === "loading" ? "Оновлюємо касову зміну — операції тимчасово недоступні" : effectiveCashActionState === "error" ? "Касові операції недоступні до успішного оновлення зміни" : effectiveCashActionState === "foreign" ? "Касові операції проводить власник поточної зміни" : "Для касових операцій відкрийте власну зміну"}</span>}
          </div>
        </header>

        {exportError === null ? null : <div className="form-message form-message--error finance-operation-message finance-operation-export-message" role="alert"><Icon name="warning" /><span>{exportError}</span><button className="text-action" onClick={() => { void exportOperations(); }} type="button">Повторити export</button></div>}
        {exportStatus === null ? null : <div className="form-message form-message--success finance-operation-message finance-operation-export-message" role="status"><Icon name="check" /><span>{exportStatus}</span></div>}

        <form className="finance-operation-filters" onSubmit={applyFilters}>
          <label className="form-field finance-operation-search"><span>Пошук</span><span className="input-with-icon"><Icon name="search" /><input maxLength={255} onChange={(event) => { setSearch(event.target.value); }} placeholder="Пацієнт, телефон або номер" value={search} /></span></label>
          <label className="form-field"><span>Тип</span><select onChange={(event) => { setType(event.target.value as TypeFilter); }} value={type}><option value="all">Усі типи</option><option value="PAYMENT">Оплата прийому</option><option value="REFUND">Повернення</option><option value="DEPOSIT">Внесення</option><option value="WITHDRAWAL">Вилучення</option></select></label>
          <label className="form-field"><span>Статус</span><select onChange={(event) => { setStatus(event.target.value as StatusFilter); }} value={status}><option value="all">Усі статуси</option><option value="OPEN">Очікує оплати</option><option value="PAID">Оплачено</option><option value="REFUNDED">Повернено</option><option value="POSTED">Проведено</option></select></label>
          <label className="form-field"><span>Спосіб</span><select onChange={(event) => { setMethod(event.target.value as MethodFilter); }} value={method}><option value="all">Усі способи</option><option value="CASH">Готівка</option><option value="CARD">Картка</option><option value="TRANSFER">Переказ</option></select></label>
          <label className="form-field"><span>Від дати</span><input onChange={(event) => { setDateFrom(event.target.value); setFilterError(null); }} type="date" value={dateFrom} /></label>
          <label className="form-field"><span>До дати</span><input onChange={(event) => { setDateTo(event.target.value); setFilterError(null); }} type="date" value={dateTo} /></label>
          <div className="finance-operation-filter-actions"><button aria-label="Скинути фільтри фінансових операцій" className="icon-button" disabled={!canResetFilters} onClick={resetFilters} type="button"><Icon name="refresh" /></button><button className="button button--secondary" type="submit">Застосувати</button></div>
        </form>

        {filterError === null ? null : <div className="form-message form-message--error finance-operation-message" role="alert"><Icon name="warning" /><span>{filterError}</span></div>}
        {error === null ? null : <div className="form-message form-message--error finance-operation-message" role="alert"><Icon name="warning" /><span>{error}</span><button className="text-action" onClick={() => { void load(query); }} type="button">Повторити</button></div>}

        {isLoading && operations.length === 0 ? <div aria-label="Завантаження фінансових операцій" className="finance-operations-loading" role="status"><span className="spinner" /><p>Завантажуємо фінансові операції…</p></div> : null}
        {!isLoading && error === null && operations.length === 0 ? <div className="finance-operations-empty"><Icon name="empty" /><h3>{appliedFiltersActive ? "Операцій за фільтрами не знайдено" : "Фінансових операцій ще немає"}</h3><p>{appliedFiltersActive ? "Змініть критерії або скиньте фільтри." : "Завершені прийоми з’являться тут зі статусом очікування оплати."}</p>{appliedFiltersActive ? <button className="button button--secondary" onClick={resetFilters} type="button">Скинути фільтри</button> : null}</div> : null}

        {operations.length > 0 ? (
          <>
            <p className="finance-operation-table__scroll-hint" id="finance-operation-table-scroll-hint"><Icon name="chevron" />Прокрутіть таблицю горизонтально, щоб переглянути всі стовпці.</p>
            <div aria-describedby="finance-operation-table-scroll-hint" aria-label="Список фінансових операцій" className="finance-operation-table" role="table" tabIndex={0}>
              <div className="finance-operation-table__head" role="row"><span role="columnheader">Дата / номер</span><span role="columnheader">Тип</span><span role="columnheader">Пацієнт / прийом</span><span role="columnheader">Деталі</span><span role="columnheader">Спосіб</span><span role="columnheader">Працівник</span><span role="columnheader">Статус</span><span role="columnheader">Сума</span><span role="columnheader">Дії</span></div>
              {operations.map((operation) => {
                const operationContext = `${operationNumber(operation)} — ${operationPatientLabel(operation)}`;
                return <div className="finance-operation-row" key={`${operation.type}:${operation.id}`} role="row">
                <span aria-label={`Дата: ${shortDateTimeFormatter.format(new Date(operation.occurred_at))}. Номер: ${operationNumber(operation)}`} data-label="Дата / номер" role="cell"><strong>{shortDateTimeFormatter.format(new Date(operation.occurred_at))}</strong><small>{operationNumber(operation)}</small></span>
                <span aria-label={`Тип: ${typeLabels[operation.type]}`} data-label="Тип" role="cell"><b className={`finance-operation-type finance-operation-type--${operation.type.toLocaleLowerCase()}`}>{typeLabels[operation.type]}</b></span>
                <span aria-label={`Пацієнт або каса: ${operationPatientLabel(operation)}. ${operationPatientMeta(operation)}`} data-label="Пацієнт / прийом" role="cell"><strong>{operationPatientLabel(operation)}</strong><small>{operationPatientMeta(operation)}</small></span>
                <span aria-label={`Деталі: ${serviceSummary(operation)}`} data-label="Деталі" role="cell"><strong>{serviceSummary(operation)}</strong><small>{isCashAdjustmentOperation(operation) ? "Службова касова операція" : operation.visit.specialist.name}</small></span>
                <span aria-label={`Спосіб: ${operationMethod(operation)}`} data-label="Спосіб" role="cell">{operationMethod(operation)}</span>
                <span aria-label={`Працівник: ${operationActorLabel(operation)}`} data-label="Працівник" role="cell"><strong>{operationActorLabel(operation)}</strong><small>{operationShiftNumber(operation) ?? "—"}</small></span>
                <span aria-label={`Статус: ${operationStatusLabel(operation)}`} data-label="Статус" role="cell"><b className={`finance-operation-status finance-operation-status--${operation.status.toLocaleLowerCase()}`}>{operationStatusLabel(operation)}</b></span>
                <span aria-label={`Сума: ${operationAmount(operation)}`} className={operation.type === "REFUND" || operation.type === "WITHDRAWAL" ? "finance-operation-amount finance-operation-amount--out" : "finance-operation-amount"} data-label="Сума" role="cell">{operationAmount(operation)}</span>
                <span className="finance-operation-row__action" data-label="Дії" role="cell"><button aria-label={`Відкрити деталі ${operationContext}`} className="icon-button" onClick={(event) => { detailTriggerRef.current = event.currentTarget; setDetail(operation); }} type="button"><Icon name="chevron" /></button>{isPayableOperation(operation) && mutationActionsAvailable ? <button aria-label={`Оплатити ${operationContext}`} className="finance-operation-pay-action" onClick={(event) => { openPayment(operation, event.currentTarget); }} type="button">Оплатити</button> : null}{isRefundableOperation(operation) && mutationActionsAvailable ? <button aria-label={`Повернути ${operationContext}`} className="finance-operation-refund-action" onClick={(event) => { openRefund(operation, event.currentTarget); }} type="button">Повернути</button> : null}</span>
              </div>;
              })}
            </div>
          </>
        ) : null}

        {nextCursor === null ? null : <footer className="finance-operations__footer"><button className="button button--secondary" disabled={isLoading} onClick={() => { void load({ ...query, cursor: nextCursor }, true); }} type="button">{isLoading ? "Завантажуємо…" : "Показати наступні операції"}</button></footer>}
      </section>

      {isDetailLoading ? <div className="finance-operation-deep-link-state" role="status"><span className="spinner" />Завантажуємо фінансову операцію…</div> : null}
      {detailError === null ? null : <div className="finance-operation-deep-link-state finance-operation-deep-link-state--error" role="alert"><Icon name="warning" /><span>{detailError.message}{detailError.correlationId === "" ? null : <small>Код запиту: {detailError.correlationId}</small>}</span>{requestedPaymentId === null ? null : <button className="button button--secondary" onClick={() => { void loadRequestedOperation(requestedPaymentId); }} type="button">Повторити</button>}<button className="button button--secondary" onClick={closeDetail} type="button">Закрити</button></div>}
      {detail === null ? null : <OperationDetailDialog hasOpenShift={mutationActionsAvailable} onClose={closeDetail} onPay={(operation) => { openPayment(operation); }} onRefund={(operation) => { openRefund(operation); }} operation={detail} />}
      {paymentInitial === undefined ? null : <PaymentDialog actionsEnabled={mutationActionsAvailable} initialOperation={paymentInitial} onClose={closePayment} onConflictRefresh={refreshAll} onSuccess={paymentSucceeded} />}
      {receiptOperation === null ? null : <PaymentReceiptDialog onClose={closeReceipt} operation={receiptOperation} />}
      {refundInitial === undefined ? null : <RefundDialog actionsEnabled={mutationActionsAvailable} availableCashMinor={availableCashMinor} initialOperation={refundInitial} onClose={closeRefund} onConflictRefresh={refreshAll} onSuccess={refundSucceeded} />}
      {cashMovementType === null ? null : <CashMovementDialog actionsEnabled={mutationActionsAvailable} availableCashMinor={availableCashMinor} movementType={cashMovementType} onClose={closeCashMovement} onConflictRefresh={refreshAll} onSuccess={cashMovementSucceeded} />}
    </>
  );
}
