import { useCallback, useEffect, useRef, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";
import { useFinanceDialogLifecycle } from "./dialogLifecycle";
import { money, parseMoneyToMinor } from "./financeFormat";
import type {
  CashMovementCreateRequest,
  CashMovementCreateResponse,
  CashMovementType,
} from "./financeTypes";

interface CashMovementDialogProps {
  readonly actionsEnabled: boolean;
  readonly availableCashMinor: number;
  readonly movementType: CashMovementType;
  readonly onClose: () => void;
  readonly onConflictRefresh: () => Promise<void>;
  readonly onSuccess: (
    operation: CashMovementCreateResponse["operation"],
    replayed: CashMovementCreateResponse["replayed"],
  ) => Promise<void>;
}

const movementLabels = {
  DEPOSIT: {
    eyebrow: "Каса · Службове внесення",
    title: "Внести готівку",
    description: "Зафіксуйте готівку, яку додаєте до поточної касової зміни.",
    review: "Підтвердити внесення?",
    submit: "Внести",
  },
  WITHDRAWAL: {
    eyebrow: "Каса · Службове вилучення",
    title: "Вилучити готівку",
    description: "Зафіксуйте готівку, яку забираєте з поточної касової зміни.",
    review: "Підтвердити вилучення?",
    submit: "Вилучити",
  },
} as const;

export function CashMovementDialog({
  actionsEnabled,
  availableCashMinor,
  movementType,
  onClose,
  onConflictRefresh,
  onSuccess,
}: CashMovementDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const amountRef = useRef<HTMLInputElement>(null);
  const reviewBackRef = useRef<HTMLButtonElement>(null);
  const continueEditingRef = useRef<HTMLButtonElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const idempotencyKey = useRef(crypto.randomUUID());
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [stage, setStage] = useState<"form" | "review">("form");
  const [showDiscard, setShowDiscard] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRetryLocked, setIsRetryLocked] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [conflictCode, setConflictCode] = useState<string | null>(null);
  const [showValidation, setShowValidation] = useState(false);
  const amountMinor = parseMoneyToMinor(amount);
  const dirty = amount !== "" || reason !== "" || comment !== "";
  const insufficientCash = movementType === "WITHDRAWAL" && amountMinor !== null && amountMinor > availableCashMinor;
  const controlsLocked = !actionsEnabled || isSubmitting || isRetryLocked || conflictCode !== null;
  const labels = movementLabels[movementType];

  const focusForm = useCallback(() => {
    window.setTimeout(() => { amountRef.current?.focus(); }, 0);
  }, []);

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

  useFinanceDialogLifecycle({ dialogRef, initialFocusRef: amountRef, onEscape: requestClose });

  useEffect(() => {
    if (showDiscard) window.setTimeout(() => { continueEditingRef.current?.focus(); }, 0);
  }, [showDiscard]);

  useEffect(() => {
    if (stage === "review") window.setTimeout(() => { reviewBackRef.current?.focus(); }, 0);
  }, [stage]);

  useEffect(() => {
    if (submitError !== null) window.setTimeout(() => { errorRef.current?.focus(); }, 0);
  }, [submitError]);

  const prepareReview = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    setShowValidation(true);
    if (amountMinor === null || reason.trim() === "" || insufficientCash || controlsLocked) return;
    setSubmitError(null);
    setStage("review");
  };

  const submit = async () => {
    if (!actionsEnabled || amountMinor === null || reason.trim() === "" || insufficientCash || conflictCode !== null) return;
    setIsSubmitting(true);
    setSubmitError(null);
    const body: CashMovementCreateRequest = {
      type: movementType,
      amount_minor: amountMinor,
      reason: reason.trim(),
      comment: comment.trim(),
    };
    const response = await apiClient.POST("/api/v1/cash-movements", {
      body,
      headers: csrfHeaders(),
      params: { header: { "Idempotency-Key": idempotencyKey.current } },
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
    if (code === "cash_shift_required") {
      setConflictCode(code);
      await onConflictRefresh();
    }
  };

  const projectedCash = amountMinor === null
    ? availableCashMinor
    : movementType === "DEPOSIT" ? availableCashMinor + amountMinor : availableCashMinor - amountMinor;

  return (
    <div className="modal-layer finance-cash-movement-layer" onMouseDown={(event) => { if (event.currentTarget === event.target) requestClose(); }} role="presentation">
      <section aria-busy={isSubmitting} aria-labelledby="finance-cash-movement-title" aria-modal="true" className="modal-card finance-cash-movement-dialog" ref={dialogRef} role="dialog" tabIndex={-1}>
        {showDiscard ? (
          <div className="finance-payment-discard"><span className="finance-payment-discard__icon"><Icon name="warning" /></span><p className="eyebrow">Незавершена касова операція</p><h2 id="finance-cash-movement-title">Відхилити введені дані?</h2><p>Сума, причина та коментар буде втрачено.</p><div><button className="button button--secondary" onClick={() => { setShowDiscard(false); focusForm(); }} ref={continueEditingRef} type="button">Продовжити заповнення</button><button className="button button--danger" onClick={onClose} type="button">Відхилити дані</button></div></div>
        ) : stage === "review" && amountMinor !== null ? (
          <div className={movementType === "WITHDRAWAL" ? "finance-destructive-review" : "finance-cash-review"}>
            <header><span><Icon name={movementType === "WITHDRAWAL" ? "warning" : "finance"} /></span><div><p className="eyebrow">Append-only касова операція</p><h2 id="finance-cash-movement-title">{labels.review}</h2><p>Після проведення запис не можна редагувати або видалити.</p></div><button aria-label={`Закрити форму: ${labels.title.toLocaleLowerCase("uk")}`} className="icon-button finance-review-close" disabled={isSubmitting || isRetryLocked} onClick={requestClose} type="button"><Icon name="close" /></button></header>
            <section className="finance-review-operation"><div><span>{movementType === "DEPOSIT" ? "Буде внесено" : "Буде вилучено"}</span><strong>{reason.trim()}</strong><small>Без пацієнта · без способу оплати</small></div><b>{movementType === "DEPOSIT" ? "+" : "−"}{money(amountMinor)}</b></section>
            <dl className="finance-review-facts"><div><dt>Доступно зараз</dt><dd>{money(availableCashMinor)}</dd></div><div><dt>Очікувана готівка після операції</dt><dd>{money(Math.max(0, projectedCash))}</dd></div>{comment.trim() === "" ? null : <div><dt>Коментар</dt><dd>{comment.trim()}</dd></div>}</dl>
            {submitError === null ? null : <div className="form-message form-message--error" ref={errorRef} role="alert" tabIndex={-1}><Icon name="warning" /><span>{submitError}</span></div>}
            <footer className="modal-card__footer"><button className="button button--secondary" disabled={isSubmitting || isRetryLocked} onClick={() => { setStage("form"); focusForm(); }} ref={reviewBackRef} type="button">Назад до форми</button><button className={movementType === "WITHDRAWAL" ? "button button--danger" : "button button--primary"} disabled={!actionsEnabled || isSubmitting} onClick={() => { void submit(); }} type="button">{isSubmitting ? "Проводимо…" : isRetryLocked ? "Повторити той самий запит" : `${labels.submit} ${money(amountMinor)}`}</button></footer>
          </div>
        ) : (
          <form onSubmit={prepareReview}>
            <header className="modal-card__header"><div><p className="eyebrow">{labels.eyebrow}</p><h2 id="finance-cash-movement-title">{labels.title}</h2><p>{labels.description}</p></div><button aria-label={`Закрити форму: ${labels.title.toLocaleLowerCase("uk")}`} className="icon-button" disabled={isSubmitting || isRetryLocked} onClick={requestClose} type="button"><Icon name="close" /></button></header>
            <section className="finance-cash-available" aria-label="Доступна готівка"><span><Icon name="finance" /></span><div><small>Доступна готівка поточної зміни</small><strong>{money(availableCashMinor)}</strong></div></section>
            <div className="finance-cash-fields">
              <label className="form-field"><span>Сума</span><span className="finance-money-input"><input aria-describedby={showValidation && amountMinor === null ? "finance-cash-amount-error" : undefined} aria-invalid={showValidation && amountMinor === null} aria-label="Сума" autoComplete="off" disabled={controlsLocked} inputMode="decimal" maxLength={18} onChange={(event) => { setAmount(event.target.value); setSubmitError(null); }} placeholder="0,00" ref={amountRef} value={amount} /><b>грн</b></span>{showValidation && amountMinor === null ? <small className="field-error" id="finance-cash-amount-error">Вкажіть додатну суму до двох знаків після коми.</small> : null}</label>
              <label className="form-field"><span>Причина</span><input aria-describedby={showValidation && reason.trim() === "" ? "finance-cash-reason-error" : undefined} aria-invalid={showValidation && reason.trim() === ""} aria-label="Причина" disabled={controlsLocked} maxLength={500} onChange={(event) => { setReason(event.target.value); setSubmitError(null); }} placeholder={movementType === "DEPOSIT" ? "Наприклад, розмінні кошти" : "Наприклад, інкасація"} required value={reason} />{showValidation && reason.trim() === "" ? <small className="field-error" id="finance-cash-reason-error">Вкажіть причину операції.</small> : null}</label>
            </div>
            <label className="form-field finance-payment-comment"><span>Коментар <small>Необов’язково</small></span><textarea disabled={controlsLocked} maxLength={2000} onChange={(event) => { setComment(event.target.value); }} placeholder="Додаткова інформація про операцію" rows={3} value={comment} /></label>
            {insufficientCash && submitError === null ? <div className="form-message form-message--error finance-payment-error" role="alert"><Icon name="warning" /><span>Не можна вилучити {money(amountMinor)}: у зміні доступно {money(availableCashMinor)}.</span></div> : null}
            {submitError === null ? null : <div className="form-message form-message--error finance-payment-error" ref={errorRef} role="alert" tabIndex={-1}><Icon name="warning" /><span>{submitError}</span>{conflictCode === "cash_shift_required" ? <button className="text-action" onClick={onClose} type="button">Повернутися до каси</button> : null}</div>}
            <footer className="modal-card__footer finance-payment-footer"><button className="button button--secondary" disabled={isSubmitting} onClick={requestClose} type="button">Скасувати</button><button className={movementType === "WITHDRAWAL" ? "button button--danger" : "button button--primary"} disabled={amountMinor === null || reason.trim() === "" || insufficientCash || controlsLocked} type="submit">Перейти до підтвердження</button></footer>
          </form>
        )}
      </section>
    </div>
  );
}
