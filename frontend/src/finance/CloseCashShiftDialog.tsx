import { useCallback, useEffect, useRef, useState, type SyntheticEvent } from "react";

import { Icon } from "../app/Icon";
import { closeCashShift, getCashShift, getCashShiftClosePreview } from "./cashShiftApi";
import type {
  CashShiftClosePreview,
  CashShiftCloseRequest,
  CashShiftCloseResponse,
} from "./cashShiftTypes";
import { useFinanceDialogLifecycle } from "./dialogLifecycle";
import { money, parseNonNegativeMoneyToMinor } from "./financeFormat";

interface CloseCashShiftDialogProps {
  readonly shiftId: string;
  readonly shiftNumber: string;
  readonly onClose: () => void;
  readonly onSuccess: (result: CashShiftCloseResponse) => Promise<void> | void;
}

interface FrozenCloseRequest {
  readonly body: CashShiftCloseRequest;
  readonly key: string;
}

function discrepancyLabel(discrepancyMinor: number): string {
  if (discrepancyMinor === 0) return "Каса зійшлася";
  if (discrepancyMinor > 0) return `Надлишок +${money(discrepancyMinor)}`;
  return `Нестача −${money(Math.abs(discrepancyMinor))}`;
}

export function CloseCashShiftDialog({
  shiftId,
  shiftNumber,
  onClose,
  onSuccess,
}: CloseCashShiftDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const actualRef = useRef<HTMLInputElement>(null);
  const continueRef = useRef<HTMLButtonElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const requestSequence = useRef(0);
  const idempotencyKey = useRef(crypto.randomUUID());
  const [preview, setPreview] = useState<CashShiftClosePreview | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(true);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [actual, setActual] = useState("");
  const [comment, setComment] = useState("");
  const [counted, setCounted] = useState(false);
  const [showValidation, setShowValidation] = useState(false);
  const [showDiscard, setShowDiscard] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [frozenRequest, setFrozenRequest] = useState<FrozenCloseRequest | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const actualMinor = parseNonNegativeMoneyToMinor(actual);
  const expectedCashMinor = preview?.shift.totals.expected_cash_minor ?? null;
  const openingSource = preview === null
    ? "—"
    : preview.shift.opening_source_shift === null
      ? preview.shift.opening_basis === "LEGACY" ? "історична зміна" : "перша зміна каси"
      : preview.shift.opening_source_shift.public_number;
  const discrepancyMinor = actualMinor === null || expectedCashMinor === null
    ? null
    : actualMinor - expectedCashMinor;
  const commentRequired = discrepancyMinor !== null && discrepancyMinor !== 0;
  const commentValid = !commentRequired || comment.trim() !== "";
  const dirty = actual !== "" || comment !== "" || counted;
  const controlsLocked = isSubmitting || frozenRequest !== null;
  const canSubmit = preview?.shift.status === "OPEN"
    && !isLoadingPreview
    && previewError === null
    && actualMinor !== null
    && counted
    && commentValid
    && !isSubmitting;

  const loadPreview = useCallback(async (afterConflict = false) => {
    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    setIsLoadingPreview(true);
    setPreviewError(null);
    if (afterConflict) setPreview(null);
    const response = await getCashShiftClosePreview(shiftId).catch(() => null);
    if (sequence !== requestSequence.current) return;
    setIsLoadingPreview(false);
    if (response === null) {
      setPreviewError("Немає зв’язку із сервером. Не вдалося перевірити касу.");
      return;
    }
    if (!response.ok) {
      setPreviewError(response.error.message);
      return;
    }
    setPreview(response.data);
    if (afterConflict) {
      setSubmitError("У зміні з’явилися нові операції. Підсумок оновлено — перерахуйте та підтвердьте касу ще раз.");
    }
  }, [shiftId]);

  useEffect(() => { void loadPreview(); }, [loadPreview]);

  useEffect(() => {
    if (!isLoadingPreview && preview !== null && !showDiscard) {
      window.setTimeout(() => { actualRef.current?.focus(); }, 0);
    }
  }, [isLoadingPreview, preview, showDiscard]);

  useEffect(() => {
    if (showDiscard) window.setTimeout(() => { continueRef.current?.focus(); }, 0);
  }, [showDiscard]);

  useEffect(() => {
    if (submitError !== null) window.setTimeout(() => { errorRef.current?.focus(); }, 0);
  }, [submitError]);

  const requestClose = useCallback(() => {
    if (isSubmitting || frozenRequest !== null) return;
    if (showDiscard) {
      setShowDiscard(false);
      window.setTimeout(() => { actualRef.current?.focus(); }, 0);
      return;
    }
    if (dirty) {
      setShowDiscard(true);
      return;
    }
    onClose();
  }, [dirty, frozenRequest, isSubmitting, onClose, showDiscard]);

  useFinanceDialogLifecycle({ dialogRef, initialFocusRef: actualRef, onEscape: requestClose });

  const submit = async (event?: SyntheticEvent) => {
    event?.preventDefault();
    setShowValidation(true);
    if (!canSubmit && frozenRequest === null) return;

    const request = frozenRequest ?? (
      actualMinor === null || preview === null
        ? null
        : {
            body: {
              actual_cash_minor: actualMinor,
              expected_operations_count: preview.shift.totals.operations_count,
              cash_count_confirmed: true,
              comment: comment.trim(),
            },
            key: idempotencyKey.current,
          }
    );
    if (request === null) return;

    setIsSubmitting(true);
    setSubmitError(null);
    const response = await closeCashShift(shiftId, request.body, request.key).catch(() => null);
    if (response === null) {
      setFrozenRequest(request);
      setIsSubmitting(false);
      setSubmitError("Немає зв’язку із сервером. Дані та ключ заблоковано — повторіть той самий запит.");
      return;
    }
    if (response.ok) {
      await onSuccess(response.data);
      return;
    }

    if (response.status >= 500 || response.error.code === "invalid_response") {
      setFrozenRequest(request);
      setIsSubmitting(false);
      setSubmitError("Сервер не підтвердив результат. Дані та ключ заблоковано — повторіть той самий запит.");
      return;
    }

    if (response.error.code === "cash_shift_already_closed") {
      setFrozenRequest(null);
      const detailResponse = await getCashShift(shiftId).catch(() => null);
      if (detailResponse?.ok && detailResponse.data.status === "CLOSED") {
        await onSuccess({ shift: detailResponse.data, replayed: true });
        return;
      }
      setIsSubmitting(false);
      setSubmitError(detailResponse === null
        ? "Зміну вже закрито, але немає зв’язку для завантаження підсумку. Повторіть пізніше."
        : detailResponse.ok
          ? "Сервер повідомив про закриття, але актуальний стан зміни не підтверджено."
          : detailResponse.error.message);
      return;
    }

    setIsSubmitting(false);
    setFrozenRequest(null);
    idempotencyKey.current = crypto.randomUUID();
    if (response.error.code === "cash_shift_changed") {
      setCounted(false);
      setShowValidation(false);
      await loadPreview(true);
      return;
    }
    setSubmitError(response.error.message);
  };

  return (
    <div
      className="modal-layer finance-close-shift-layer"
      onMouseDown={(event) => { if (event.currentTarget === event.target) requestClose(); }}
      role="presentation"
    >
      <section
        aria-busy={isLoadingPreview || isSubmitting}
        aria-labelledby="finance-close-shift-title"
        aria-modal="true"
        className="modal-card finance-close-shift-dialog"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        {showDiscard ? (
          <div className="finance-payment-discard">
            <span className="finance-payment-discard__icon"><Icon name="warning" /></span>
            <p className="eyebrow">Незавершена звірка</p>
            <h2 id="finance-close-shift-title">Відхилити введені дані?</h2>
            <p>Фактична сума, коментар і підтвердження перерахунку буде втрачено.</p>
            <div>
              <button className="button button--secondary" onClick={() => { setShowDiscard(false); }} ref={continueRef} type="button">Продовжити звірку</button>
              <button className="button button--danger" onClick={onClose} type="button">Відхилити дані</button>
            </div>
          </div>
        ) : (
          <form onSubmit={(event) => { void submit(event); }}>
            <header className="modal-card__header">
              <div>
                <p className="eyebrow">Каса · Завершення роботи</p>
                <h2 id="finance-close-shift-title">Закрити касову зміну?</h2>
                <p>{shiftNumber} · після закриття нові операції в цю зміну неможливі.</p>
              </div>
              <button aria-label="Закрити звірку касової зміни" className="icon-button" disabled={controlsLocked} onClick={requestClose} type="button"><Icon name="close" /></button>
            </header>

            {isLoadingPreview && preview === null ? (
              <div aria-label="Завантаження підсумку зміни" className="finance-close-preview-loading" role="status"><span className="spinner" /><p>Звіряємо актуальний ledger…</p></div>
            ) : null}

            {!isLoadingPreview && previewError !== null ? (
              <div className="finance-close-preview-error" role="alert">
                <Icon name="warning" /><div><strong>Не вдалося підготувати звірку</strong><p>{previewError}</p></div>
                <button className="button button--secondary" onClick={() => { void loadPreview(); }} type="button"><Icon name="refresh" />Повторити</button>
              </div>
            ) : null}

            {preview === null ? null : (
              <>
                <section aria-label="Підсумок касової зміни" className="finance-close-summary">
                  <div><span>Виторг</span><strong>{money(preview.shift.totals.revenue_minor)}</strong></div>
                  <div><span>Готівка</span><strong>{money(preview.shift.totals.cash_payments_minor - preview.shift.totals.cash_refunds_minor)}</strong></div>
                  <div><span>Картка</span><strong>{money(preview.shift.totals.card_payments_minor - preview.shift.totals.card_refunds_minor)}</strong></div>
                  <div><span>Операції</span><strong>{preview.shift.totals.operations_count}</strong></div>
                </section>

                {preview.unpaid.count > 0 ? (
                  <div className="form-message form-message--warning finance-close-unpaid" role="status">
                    <Icon name="warning" />
                    <span>Є неоплачені прийоми: {preview.unpaid.count} на {money(preview.unpaid.total_minor)}. Це попередження не блокує закриття.</span>
                  </div>
                ) : null}

                <section className="finance-reconciliation" aria-labelledby="finance-reconciliation-title">
                  <header><div><p className="eyebrow">Фізична готівка</p><h3 id="finance-reconciliation-title">Звірка каси</h3></div><span><small>Очікується</small><strong>{money(preview.shift.totals.expected_cash_minor)}</strong><small>Початок {money(preview.shift.opening_cash_minor)} · {openingSource}</small></span></header>
                  <label className="form-field finance-actual-cash">
                    <span>Фактично в касі</span>
                    <span className="finance-money-input"><input
                      aria-label="Фактично в касі"
                      aria-describedby={showValidation && actualMinor === null ? "finance-actual-cash-error" : undefined}
                      aria-invalid={showValidation && actualMinor === null}
                      autoComplete="off"
                      disabled={controlsLocked}
                      inputMode="decimal"
                      maxLength={18}
                      onChange={(event) => {
                        setActual(event.target.value);
                        setCounted(false);
                        setSubmitError(null);
                      }}
                      placeholder="0,00"
                      ref={actualRef}
                      value={actual}
                    /><b>грн</b></span>
                    {showValidation && actualMinor === null ? <small className="field-error" id="finance-actual-cash-error">Вкажіть суму від 0 до двох знаків після коми.</small> : null}
                  </label>

                  <div
                    aria-live="polite"
                    className={`finance-discrepancy${discrepancyMinor === null ? "" : discrepancyMinor === 0 ? " finance-discrepancy--balanced" : discrepancyMinor > 0 ? " finance-discrepancy--excess" : " finance-discrepancy--shortage"}`}
                  >
                    <span><Icon name={discrepancyMinor === 0 ? "check" : "finance"} /></span>
                    <div><small>Різниця</small><strong>{discrepancyMinor === null ? "Введіть фактичну суму" : discrepancyLabel(discrepancyMinor)}</strong></div>
                    <b>{discrepancyMinor === null ? "—" : discrepancyMinor === 0 ? money(0) : `${discrepancyMinor > 0 ? "+" : "−"}${money(Math.abs(discrepancyMinor))}`}</b>
                  </div>

                  <label className="form-field finance-close-comment">
                    <span>Коментар <small>{commentRequired ? "Обов’язково при розбіжності" : "Необов’язково"}</small></span>
                    <textarea
                      aria-describedby={showValidation && !commentValid ? "finance-close-comment-error" : undefined}
                      aria-invalid={showValidation && !commentValid}
                      disabled={controlsLocked}
                      maxLength={2000}
                      onChange={(event) => { setComment(event.target.value); setSubmitError(null); }}
                      placeholder={commentRequired ? "Поясніть надлишок або нестачу" : "Додаткова інформація про звірку"}
                      rows={3}
                      value={comment}
                    />
                    {showValidation && !commentValid ? <small className="field-error" id="finance-close-comment-error">Поясніть причину розбіжності.</small> : null}
                  </label>

                  <label className="finance-counted-confirmation">
                    <input checked={counted} disabled={controlsLocked || actualMinor === null} onChange={(event) => { setCounted(event.target.checked); setSubmitError(null); }} type="checkbox" />
                    <span><strong>Готівку перераховано</strong><small>Підтверджую фактичну суму перед незворотним закриттям зміни.</small></span>
                  </label>
                </section>
              </>
            )}

            {submitError === null ? null : <div className="form-message form-message--error finance-close-error" ref={errorRef} role="alert" tabIndex={-1}><Icon name="warning" /><span>{submitError}</span></div>}

            <footer className="modal-card__footer finance-close-footer">
              <button className="button button--secondary" disabled={controlsLocked} onClick={requestClose} type="button">Скасувати</button>
              <button className="button button--danger" disabled={frozenRequest === null ? !canSubmit : isSubmitting} type="submit">
                {isSubmitting ? "Закриваємо…" : frozenRequest !== null ? "Повторити той самий запит" : "Закрити зміну"}
              </button>
            </footer>
          </form>
        )}
      </section>
    </div>
  );
}
