import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type SyntheticEvent,
} from "react";

import { apiClient } from "../api/client";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";
import { useFinanceDialogLifecycle } from "./dialogLifecycle";
import { dateTimeFormatter, methodLabels, money, parseMoneyToMinor, shortDateTimeFormatter } from "./financeFormat";
import type {
  FinanceOperation,
  FinancePaymentOperation,
  RefundCreateRequest,
  RefundCreateResponse,
} from "./financeTypes";

function isRefundablePayment(operation: FinanceOperation): operation is FinancePaymentOperation {
  return operation.type === "PAYMENT"
    && operation.status === "PAID"
    && operation.amount_minor > 0
    && operation.payment !== null
    && operation.refund === null;
}

interface RefundDialogProps {
  readonly actionsEnabled: boolean;
  readonly availableCashMinor: number;
  readonly initialOperation: FinancePaymentOperation | null;
  readonly onClose: () => void;
  readonly onConflictRefresh: () => Promise<void>;
  readonly onSuccess: (
    operation: RefundCreateResponse["operation"],
    replayed: RefundCreateResponse["replayed"],
  ) => Promise<void>;
}

export function RefundDialog({
  actionsEnabled,
  availableCashMinor,
  initialOperation,
  onClose,
  onConflictRefresh,
  onSuccess,
}: RefundDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const reviewBackRef = useRef<HTMLButtonElement>(null);
  const continueEditingRef = useRef<HTMLButtonElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const idempotencyKey = useRef(crypto.randomUUID());
  const requestSequence = useRef(0);
  const [query, setQuery] = useState(initialOperation?.patient.display_name ?? "");
  const [date, setDate] = useState("");
  const [amountFilter, setAmountFilter] = useState("");
  const [results, setResults] = useState<readonly FinancePaymentOperation[]>(initialOperation === null ? [] : [initialOperation]);
  const [selected, setSelected] = useState<FinancePaymentOperation | null>(initialOperation);
  const [reason, setReason] = useState("");
  const [stage, setStage] = useState<"form" | "review">("form");
  const [isSearching, setIsSearching] = useState(initialOperation === null);
  const [isResultsOpen, setIsResultsOpen] = useState(initialOperation === null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [filterError, setFilterError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [conflictCode, setConflictCode] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRetryLocked, setIsRetryLocked] = useState(false);
  const [showDiscard, setShowDiscard] = useState(false);
  const initialQuery = initialOperation?.patient.display_name ?? "";
  const dirty = selected !== initialOperation
    || query !== initialQuery
    || date !== ""
    || amountFilter !== ""
    || reason !== "";
  const selectedPayment = selected?.payment ?? null;
  const isCashRefund = selectedPayment?.payment_method === "CASH";
  const insufficientCash = isCashRefund && selected !== null && selected.amount_minor > availableCashMinor;
  const controlsLocked = !actionsEnabled || isSubmitting || isRetryLocked || conflictCode !== null;

  const focusForm = useCallback(() => {
    window.setTimeout(() => { (selected === null ? searchRef.current : reasonRef.current)?.focus(); }, 0);
  }, [selected]);

  const requestClose = useCallback(() => {
    if (isSubmitting || isRetryLocked) return;
    if (stage === "review") {
      setStage("form");
      focusForm();
      return;
    }
    if (showDiscard) {
      setShowDiscard(false);
      focusForm();
      return;
    }
    if (dirty) {
      setShowDiscard(true);
      return;
    }
    onClose();
  }, [dirty, focusForm, isRetryLocked, isSubmitting, onClose, showDiscard, stage]);

  useFinanceDialogLifecycle({
    dialogRef,
    initialFocusRef: initialOperation === null ? searchRef : reasonRef,
    onEscape: requestClose,
  });

  useEffect(() => {
    if (showDiscard) window.setTimeout(() => { continueEditingRef.current?.focus(); }, 0);
  }, [showDiscard]);

  useEffect(() => {
    if (stage === "review") window.setTimeout(() => { reviewBackRef.current?.focus(); }, 0);
  }, [stage]);

  useEffect(() => {
    if (submitError !== null) window.setTimeout(() => { errorRef.current?.focus(); }, 0);
  }, [submitError]);

  const searchPayments = useCallback(async (search: string, exactDate: string, exactAmount: string) => {
    const amountMinor = exactAmount.trim() === "" ? null : parseMoneyToMinor(exactAmount);
    if (exactAmount.trim() !== "" && amountMinor === null) {
      setFilterError("Вкажіть точну суму у гривнях із не більш як двома знаками після коми.");
      setIsSearching(false);
      return;
    }
    setFilterError(null);
    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    setIsSearching(true);
    setSearchError(null);
    const response = await apiClient.GET("/api/v1/finance/operations", {
      params: {
        query: {
          type: "PAYMENT",
          status: "PAID",
          refundable_only: true,
          ...(search.trim() === "" ? {} : { search: search.trim() }),
          ...(exactDate === "" ? {} : { date_from: exactDate, date_to: exactDate }),
          ...(amountMinor === null ? {} : { amount_minor: amountMinor }),
        },
      },
    }).catch(() => null);
    if (sequence !== requestSequence.current) return;
    setIsSearching(false);
    if (response === null) {
      setSearchError("Немає зв’язку із сервером. Не вдалося знайти оплати для повернення.");
      return;
    }
    if (response.data === undefined) {
      setSearchError(response.error.message);
      return;
    }
    setResults(response.data.operations.filter(isRefundablePayment));
    setActiveIndex(0);
  }, []);

  useEffect(() => {
    if (selected !== null && query === selected.patient.display_name && date === "" && amountFilter === "") return;
    const timeout = window.setTimeout(() => { void searchPayments(query, date, amountFilter); }, 250);
    return () => { window.clearTimeout(timeout); };
  }, [amountFilter, date, query, searchPayments, selected]);

  const selectOperation = (operation: FinancePaymentOperation) => {
    setSelected(operation);
    setQuery(operation.patient.display_name);
    setResults([operation]);
    setIsResultsOpen(false);
    setSubmitError(null);
    setConflictCode(null);
    window.setTimeout(() => { reasonRef.current?.focus(); }, 0);
  };

  const chooseAnother = () => {
    idempotencyKey.current = crypto.randomUUID();
    setSelected(null);
    setQuery("");
    setDate("");
    setAmountFilter("");
    setResults([]);
    setReason("");
    setSubmitError(null);
    setConflictCode(null);
    setIsRetryLocked(false);
    setStage("form");
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

  const prepareReview = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selected === null || reason.trim() === "" || insufficientCash || controlsLocked) return;
    setSubmitError(null);
    setStage("review");
  };

  const submit = async () => {
    if (!actionsEnabled || selectedPayment === null || selected === null || reason.trim() === "" || insufficientCash || conflictCode !== null) return;
    setIsSubmitting(true);
    setSubmitError(null);
    const body: RefundCreateRequest = { reason: reason.trim() };
    const response = await apiClient.POST("/api/v1/payments/{payment_id}/refunds", {
      body,
      headers: csrfHeaders(),
      params: {
        header: { "Idempotency-Key": idempotencyKey.current },
        path: { payment_id: selectedPayment.id },
      },
    }).catch(() => null);
    if (response === null) {
      setIsSubmitting(false);
      setIsRetryLocked(true);
      setSubmitError("Немає зв’язку із сервером. Дані заблоковано — повторіть той самий запит.");
      return;
    }
    if (response.data !== undefined) {
      await onSuccess(response.data.operation, response.data.replayed);
      return;
    }
    const code = response.error.code;
    idempotencyKey.current = crypto.randomUUID();
    setIsSubmitting(false);
    setIsRetryLocked(false);
    setSubmitError(response.error.message);
    if (code === "insufficient_cash") {
      setStage("form");
      await onConflictRefresh();
      return;
    }
    if (["payment_already_refunded", "payment_not_refundable", "cash_shift_required"].includes(code)) {
      setConflictCode(code);
      await onConflictRefresh();
    }
  };

  return (
    <div className="modal-layer finance-refund-layer" onMouseDown={(event) => { if (event.currentTarget === event.target) requestClose(); }} role="presentation">
      <section aria-busy={isSubmitting} aria-labelledby="finance-refund-title" aria-modal="true" className="modal-card finance-refund-dialog" ref={dialogRef} role="dialog" tabIndex={-1}>
        {showDiscard ? (
          <div className="finance-payment-discard">
            <span className="finance-payment-discard__icon"><Icon name="warning" /></span>
            <p className="eyebrow">Незавершене повернення</p>
            <h2 id="finance-refund-title">Відхилити введені дані?</h2>
            <p>Обрана оплата та причина повернення буде втрачена.</p>
            <div><button className="button button--secondary" onClick={() => { setShowDiscard(false); focusForm(); }} ref={continueEditingRef} type="button">Продовжити заповнення</button><button className="button button--danger" onClick={onClose} type="button">Відхилити дані</button></div>
          </div>
        ) : stage === "review" && selected !== null && selectedPayment !== null ? (
          <div className="finance-destructive-review">
            <header><span><Icon name="warning" /></span><div><p className="eyebrow">Незворотна касова операція</p><h2 id="finance-refund-title">Підтвердити повне повернення?</h2><p>Буде створено окремий незмінний запис, а оплату позначено повністю поверненою.</p></div><button aria-label="Закрити форму повернення" className="icon-button finance-review-close" disabled={isSubmitting || isRetryLocked} onClick={requestClose} type="button"><Icon name="close" /></button></header>
            <section className="finance-review-operation"><div><span>Початкова оплата</span><strong>{selectedPayment.public_number}</strong><small>{selected.patient.display_name} · {methodLabels[selectedPayment.payment_method]}</small></div><b>−{money(selected.amount_minor)}</b></section>
            <dl className="finance-review-facts"><div><dt>Причина</dt><dd>{reason.trim()}</dd></div><div><dt>Касова зміна</dt><dd>Поточна власна зміна</dd></div>{isCashRefund ? <div><dt>Готівка після повернення</dt><dd>{money(Math.max(0, availableCashMinor - selected.amount_minor))}</dd></div> : <div><dt>Фізична готівка</dt><dd>Не змінюється</dd></div>}</dl>
            {submitError === null ? null : <div className="form-message form-message--error" ref={errorRef} role="alert" tabIndex={-1}><Icon name="warning" /><span>{submitError}</span></div>}
            <footer className="modal-card__footer"><button className="button button--secondary" disabled={isSubmitting || isRetryLocked} onClick={() => { setStage("form"); focusForm(); }} ref={reviewBackRef} type="button">Назад до форми</button><button className="button button--danger" disabled={!actionsEnabled || isSubmitting} onClick={() => { void submit(); }} type="button">{isSubmitting ? "Проводимо…" : isRetryLocked ? "Повторити той самий запит" : `Повернути ${money(selected.amount_minor)}`}</button></footer>
          </div>
        ) : (
          <form onSubmit={prepareReview}>
            <header className="modal-card__header"><div><p className="eyebrow">Фінанси · Повне повернення</p><h2 id="finance-refund-title">Оформити повернення</h2><p>Знайдіть початкову оплату. Суму та спосіб повернення визначає сервер.</p></div><button aria-label="Закрити форму повернення" className="icon-button" disabled={isSubmitting || isRetryLocked} onClick={requestClose} type="button"><Icon name="close" /></button></header>
            <div className="finance-refund-search-grid">
              <div className="finance-payment-search"><label htmlFor="finance-refund-search-input">Початкова оплата</label><div className="input-with-icon"><Icon name="search" /><input aria-activedescendant={isResultsOpen && results[activeIndex] !== undefined ? `finance-refund-option-${results[activeIndex].id}` : undefined} aria-autocomplete="list" aria-controls="finance-refund-results" aria-expanded={isResultsOpen} autoComplete="off" disabled={controlsLocked} id="finance-refund-search-input" maxLength={255} onChange={(event) => { setQuery(event.target.value); setSelected(null); setSubmitError(null); setConflictCode(null); setIsResultsOpen(true); }} onFocus={() => { setIsResultsOpen(true); }} onKeyDown={onSearchKeyDown} placeholder="Пацієнт, телефон або № оплати" ref={searchRef} role="combobox" value={query} /></div>
                {isResultsOpen ? <div aria-label="Оплати, доступні для повернення" className="finance-payment-results" id="finance-refund-results" role="listbox">{isSearching ? <div className="finance-payment-results__state" role="status"><span className="spinner" />Шукаємо оплати…</div> : null}{!isSearching && searchError !== null ? <div className="finance-payment-results__state finance-payment-results__state--error" role="alert"><Icon name="warning" /><span>{searchError}</span><button className="text-action" onClick={() => { void searchPayments(query, date, amountFilter); }} type="button">Повторити</button></div> : null}{!isSearching && searchError === null && filterError === null && results.length === 0 ? <div className="finance-payment-results__state"><Icon name="empty" /><span>Оплат для повернення не знайдено.</span></div> : null}{!isSearching && searchError === null && filterError === null ? results.map((operation, index) => <button aria-selected={index === activeIndex} className={index === activeIndex ? "finance-payment-option finance-payment-option--active" : "finance-payment-option"} disabled={controlsLocked} id={`finance-refund-option-${operation.id}`} key={operation.id} onClick={() => { selectOperation(operation); }} onMouseEnter={() => { setActiveIndex(index); }} role="option" tabIndex={-1} type="button"><span className="avatar" aria-hidden="true">{operation.patient.display_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("")}</span><span><strong>{operation.payment?.public_number} · {operation.patient.display_name}</strong><small>{operation.patient.public_number} · {operation.patient.phone}</small><small>{shortDateTimeFormatter.format(new Date(operation.payment?.posted_at ?? operation.occurred_at))} · {operation.payment === null ? "—" : methodLabels[operation.payment.payment_method]}</small></span><b>{money(operation.amount_minor)}</b></button>) : null}</div> : null}
              </div>
              <label className="form-field"><span>Дата оплати <small>Необов’язково</small></span><input disabled={controlsLocked} onChange={(event) => { setDate(event.target.value); setSelected(null); setIsResultsOpen(true); }} type="date" value={date} /></label>
              <label className="form-field"><span>Точна сума <small>Необов’язково</small></span><span className="finance-money-input"><input disabled={controlsLocked} inputMode="decimal" onChange={(event) => { setAmountFilter(event.target.value); setSelected(null); setIsResultsOpen(true); }} placeholder="0,00" value={amountFilter} /><b>грн</b></span></label>
            </div>
            {filterError === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{filterError}</span></div>}
            {selected === null ? <div className="finance-payment-placeholder"><Icon name="refresh" /><p>Оберіть проведену оплату, яку ще не було повернено.</p></div> : <><section className="finance-payment-summary" aria-labelledby="finance-refund-summary-title"><header><div><p className="eyebrow">Початкова оплата {selected.payment?.public_number}</p><h3 id="finance-refund-summary-title">{selected.patient.display_name}</h3><p>{selected.visit.public_number} · {dateTimeFormatter.format(new Date(selected.visit.completed_at))} · {selected.visit.specialist.name}</p></div><strong>{money(selected.amount_minor)}</strong></header><div>{selected.visit.services.map((service) => <article key={service.id}><span><strong>{service.name}</strong><small>{service.code} · {service.quantity} × {money(service.unit_price_minor)}</small></span><b>{money(service.line_total_minor)}</b></article>)}</div><footer><span>Повна сума · {selected.payment === null ? "—" : methodLabels[selected.payment.payment_method]}</span><strong>{money(selected.amount_minor)}</strong></footer></section><label className="form-field finance-refund-reason"><span>Причина повернення</span><textarea aria-invalid={reason.trim() === "" ? undefined : false} disabled={controlsLocked} maxLength={500} onChange={(event) => { setReason(event.target.value); setSubmitError(null); }} placeholder="Опишіть причину повного повернення" ref={reasonRef} required rows={3} value={reason} /></label></>}
            {insufficientCash && submitError === null ? <div className="form-message form-message--error finance-payment-error" role="alert"><Icon name="warning" /><span>Недостатньо готівки: доступно {money(availableCashMinor)}, потрібно {money(selected.amount_minor)}.</span></div> : null}
            {submitError === null ? null : <div className="form-message form-message--error finance-payment-error" ref={errorRef} role="alert" tabIndex={-1}><Icon name="warning" /><span>{submitError}</span>{conflictCode === "cash_shift_required" ? <button className="text-action" onClick={onClose} type="button">Повернутися до каси</button> : conflictCode === null ? null : <button className="text-action" onClick={chooseAnother} type="button">Обрати іншу оплату</button>}</div>}
            <footer className="modal-card__footer finance-payment-footer"><button className="button button--secondary" disabled={isSubmitting} onClick={requestClose} type="button">Скасувати</button><button className="button button--danger" disabled={selected === null || reason.trim() === "" || insufficientCash || controlsLocked} type="submit">Перейти до підтвердження</button></footer>
          </form>
        )}
      </section>
    </div>
  );
}
