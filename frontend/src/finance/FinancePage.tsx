import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { useNavigate } from "react-router";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";
import type { CashShiftCloseResponse } from "./cashShiftTypes";
import { CloseCashShiftDialog } from "./CloseCashShiftDialog";
import { FinanceOperations, type FinanceCashActionState } from "./FinanceOperations";
import { FinanceSubnav } from "./FinanceSubnav";

type CashLedgerEntry = components["schemas"]["CashLedgerEntry"];
type CashShiftProjection = components["schemas"]["CashShiftProjection"];

const moneyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
  maximumFractionDigits: 2,
});

const openedAtFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const ledgerTimeFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const kindLabels: Readonly<Record<CashLedgerEntry["kind"], string>> = {
  PAYMENT: "Оплата",
  REFUND: "Повернення",
  DEPOSIT: "Внесення",
  WITHDRAWAL: "Вилучення",
};

const methodLabels: Readonly<Record<Exclude<CashLedgerEntry["payment_method"], null>, string>> = {
  CASH: "Готівка",
  CARD: "Картка",
  TRANSFER: "Переказ",
};

const employeeRoleLabels: Readonly<Record<string, string>> = {
  admin: "Адміністратор",
  reception: "Ресепшн",
  podologist: "Подолог",
};

function money(value: number): string {
  return moneyFormatter.format(value / 100);
}

function entryAmount(entry: CashLedgerEntry): string {
  const outgoing = entry.kind === "REFUND" || entry.kind === "WITHDRAWAL";
  return `${outgoing ? "−" : "+"}${money(entry.amount_minor)}`;
}

function operationCountLabel(value: number): string {
  const lastTwo = value % 100;
  const last = value % 10;
  if (last === 1 && lastTwo !== 11) return "операція";
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return "операції";
  return "операцій";
}

function paymentCountLabel(value: number): string {
  const lastTwo = value % 100;
  const last = value % 10;
  if (last === 1 && lastTwo !== 11) return "оплата";
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return "оплати";
  return "оплат";
}

function OpenShiftDialog({
  error,
  isOpening,
  onClose,
  onConfirm,
}: {
  readonly error: string | null;
  readonly isOpening: boolean;
  readonly onClose: () => void;
  readonly onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (isOpening) dialogRef.current?.focus();
    else cancelRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!isOpening) onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled), [href], [tabindex]:not([tabindex='-1'])",
      );
      if (focusable === undefined || focusable.length === 0) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!dialogRef.current?.contains(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first)?.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpening, onClose]);

  return (
    <div
      className="modal-layer finance-open-shift-layer"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target && !isOpening) onClose();
      }}
      role="presentation"
    >
      <section
        aria-busy={isOpening}
        aria-describedby="finance-open-shift-description"
        aria-labelledby="finance-open-shift-title"
        aria-modal="true"
        className="modal-card finance-open-shift-dialog"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Каса · Початок роботи</p>
            <h2 id="finance-open-shift-title">Відкрити касову зміну?</h2>
            <p id="finance-open-shift-description">Зміна буде прив’язана до вашого облікового запису.</p>
          </div>
          <button aria-label="Закрити підтвердження" className="icon-button" disabled={isOpening} onClick={onClose} type="button"><Icon name="close" /></button>
        </header>

        <div className="finance-opening-balance">
          <span className="finance-opening-balance__icon" aria-hidden="true"><Icon name="finance" /></span>
          <span><small>Початковий залишок</small><strong>{money(0)}</strong></span>
          <p>Для MVP зміна завжди відкривається з нульовим початковим залишком. Довільна сума не вводиться.</p>
        </div>

        {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}

        <footer className="modal-card__footer">
          <button className="button button--secondary" disabled={isOpening} onClick={onClose} ref={cancelRef} type="button">Скасувати</button>
          <button className="button button--primary" disabled={isOpening} onClick={onConfirm} type="button">{isOpening ? "Відкриваємо…" : "Відкрити зміну"}</button>
        </footer>
      </section>
    </div>
  );
}

function ShiftSummary({
  closeTriggerRef,
  headingRef,
  onCloseShift,
  shift,
}: {
  readonly closeTriggerRef: RefObject<HTMLButtonElement | null>;
  readonly headingRef: RefObject<HTMLHeadingElement | null>;
  readonly onCloseShift: () => void;
  readonly shift: CashShiftProjection;
}) {
  const totals = shift.totals;
  const entries = shift.entries;

  return (
    <>
      <section className="finance-shift-hero panel" aria-labelledby="finance-current-shift-title">
        <div className="finance-shift-hero__identity">
          <span className="finance-shift-status"><span aria-hidden="true" />Відкрита</span>
          <p className="eyebrow">{shift.public_number}</p>
          <h2 id="finance-current-shift-title" ref={headingRef} tabIndex={-1}>Поточна касова зміна</h2>
          <p>Відкрита {openedAtFormatter.format(new Date(shift.opened_at))}</p>
        </div>
        <div className="finance-shift-hero__actions">
          <div className="finance-shift-owner">
            <span className="avatar" aria-hidden="true">{shift.employee.name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toLocaleUpperCase("uk")}</span>
            <span><small>Касир</small><strong>{shift.employee.name}</strong><small>{employeeRoleLabels[shift.employee.role] ?? shift.employee.role} · {shift.employee.email}</small></span>
          </div>
          <button className="button button--danger" onClick={onCloseShift} ref={closeTriggerRef} type="button">Закрити зміну</button>
        </div>
      </section>

      <section className="finance-summary-grid" aria-label="Підсумки поточної касової зміни">
        <article className="panel finance-summary-card finance-summary-card--accent"><span>Виторг</span><strong>{money(totals.revenue_minor)}</strong><small>{totals.payment_count} {paymentCountLabel(totals.payment_count)} · без службових рухів</small></article>
        <article className="panel finance-summary-card finance-summary-card--cash"><span>Очікувана готівка</span><strong>{money(totals.expected_cash_minor)}</strong><small>За ledger поточної зміни</small></article>
        <article className="panel finance-summary-card"><span>Усього оплат</span><strong>{money(totals.payments_total_minor)}</strong><small>{totals.payment_count} проведено</small></article>
        <article className="panel finance-summary-card"><span>Повернення</span><strong>{money(totals.refunds_total_minor)}</strong><small>{totals.refund_count} проведено</small></article>
      </section>

      <section className="panel finance-methods" aria-labelledby="finance-methods-title">
        <header><div><p className="eyebrow">Ledger-derived</p><h2 id="finance-methods-title">Розподіл коштів</h2><p>Підсумки обчислюються з незмінних касових операцій.</p></div><span><Icon name="lock" />Лише читання</span></header>
        <div className="finance-methods__grid">
          <article><span className="finance-method-dot finance-method-dot--cash" aria-hidden="true" /><span><small>Готівка</small><strong>{money(totals.cash_payments_minor)}</strong><small>Повернення: {money(totals.cash_refunds_minor)}</small></span></article>
          <article><span className="finance-method-dot finance-method-dot--card" aria-hidden="true" /><span><small>Картка</small><strong>{money(totals.card_payments_minor)}</strong><small>Повернення: {money(totals.card_refunds_minor)}</small></span></article>
          <article><span className="finance-method-dot finance-method-dot--transfer" aria-hidden="true" /><span><small>Переказ</small><strong>{money(totals.transfer_payments_minor)}</strong><small>Повернення: {money(totals.transfer_refunds_minor)}</small></span></article>
          <article><span className="finance-method-dot finance-method-dot--deposit" aria-hidden="true" /><span><small>Службові рухи</small><strong>+{money(totals.deposits_minor)} · −{money(totals.withdrawals_minor)}</strong><small>Внесення · вилучення</small></span></article>
        </div>
      </section>

      <section className="panel finance-ledger" aria-labelledby="finance-ledger-title">
        <header>
          <div><p className="eyebrow">Append-only</p><h2 id="finance-ledger-title">Операції зміни</h2><p>Нові операції відображаються зверху.</p></div>
          <span>{totals.operations_count} {operationCountLabel(totals.operations_count)}</span>
        </header>
        {entries.length === 0 ? (
          <div className="finance-ledger-empty"><Icon name="finance" /><h3>Операцій ще немає</h3><p>Оплати та інші касові рухи з’являться тут після проведення.</p></div>
        ) : (
          <div aria-label="Касові операції поточної зміни" className="finance-ledger-table" role="table">
            <div className="finance-ledger-head" role="row"><span role="columnheader">Дата й час</span><span role="columnheader">Операція</span><span role="columnheader">Спосіб</span><span role="columnheader">Працівник</span><span role="columnheader">Сума</span></div>
            {entries.map((entry) => {
              const outgoing = entry.kind === "REFUND" || entry.kind === "WITHDRAWAL";
              const formattedTime = ledgerTimeFormatter.format(new Date(entry.posted_at));
              const paymentMethod = entry.payment_method === null
                ? "Не застосовується"
                : methodLabels[entry.payment_method];
              const formattedAmount = entryAmount(entry);
              return (
                <div className="finance-ledger-row" key={entry.id} role="row">
                  <span aria-label={`Дата й час: ${formattedTime}. Номер: ${entry.public_number}`} data-label="Дата й час" role="cell"><strong>{formattedTime}</strong><small>{entry.public_number}</small></span>
                  <span aria-label={`Операція: ${kindLabels[entry.kind]}`} data-label="Операція" role="cell"><b className={`finance-ledger-kind finance-ledger-kind--${entry.kind.toLocaleLowerCase()}`}>{kindLabels[entry.kind]}</b></span>
                  <span aria-label={`Спосіб: ${paymentMethod}`} data-label="Спосіб" role="cell">{paymentMethod}</span>
                  <span aria-label={`Працівник: ${entry.actor_name}, ${entry.actor_email}`} data-label="Працівник" role="cell"><strong>{entry.actor_name}</strong><small>{entry.actor_email}</small></span>
                  <span aria-label={`Сума: ${formattedAmount}`} className={outgoing ? "finance-ledger-amount finance-ledger-amount--out" : "finance-ledger-amount"} data-label="Сума" role="cell">{formattedAmount}</span>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </>
  );
}

export function FinancePage() {
  const navigate = useNavigate();
  const [shift, setShift] = useState<CashShiftProjection | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isOpenDialogVisible, setIsOpenDialogVisible] = useState(false);
  const [isOpening, setIsOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);
  const [isCloseDialogVisible, setIsCloseDialogVisible] = useState(false);
  const openTriggerRef = useRef<HTMLButtonElement>(null);
  const closeTriggerRef = useRef<HTMLButtonElement>(null);
  const shiftHeadingRef = useRef<HTMLHeadingElement>(null);
  const currentRequestSequence = useRef(0);

  const loadCurrent = useCallback(async () => {
    const sequence = currentRequestSequence.current + 1;
    currentRequestSequence.current = sequence;
    setIsLoading(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/cash-shifts/current").catch(() => null);
    if (sequence !== currentRequestSequence.current) return null;
    setIsLoading(false);
    if (result === null) {
      setShift(null);
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
      return null;
    }
    if (result.data === undefined) {
      setShift(null);
      setError(result.error.message);
      return null;
    }
    setShift(result.data.shift);
    return result.data.shift;
  }, []);

  useEffect(() => { void loadCurrent(); }, [loadCurrent]);

  const closeDialog = useCallback(() => {
    if (isOpening) return;
    setIsOpenDialogVisible(false);
    setOpenError(null);
    window.setTimeout(() => { openTriggerRef.current?.focus(); }, 0);
  }, [isOpening]);

  const openShift = async () => {
    setIsOpening(true);
    setOpenError(null);
    setSuccess(null);
    const result = await apiClient.POST("/api/v1/cash-shifts", {
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result === null) {
      setOpenError("Немає зв’язку із сервером. Зміну не відкрито.");
      setIsOpening(false);
      return;
    }
    if (result.data !== undefined) {
      setShift(result.data);
      setIsOpening(false);
      setIsOpenDialogVisible(false);
      setSuccess(`Касову зміну ${result.data.public_number} відкрито.`);
      window.setTimeout(() => { shiftHeadingRef.current?.focus(); }, 0);
      return;
    }
    if (result.error.code === "cash_shift_already_open") {
      const currentResult = await apiClient.GET("/api/v1/cash-shifts/current").catch(() => null);
      setIsOpening(false);
      if (currentResult?.data?.shift) {
        setShift(currentResult.data.shift);
        setIsOpenDialogVisible(false);
        setSuccess("Відкрита зміна вже існувала. Показуємо актуальні дані.");
        window.setTimeout(() => { shiftHeadingRef.current?.focus(); }, 0);
      } else {
        setOpenError(currentResult?.error?.message ?? "Не вдалося оновити актуальну касову зміну.");
      }
      return;
    }
    setOpenError(result.error.message);
    setIsOpening(false);
  };

  const cashActionState: FinanceCashActionState = isLoading
    ? "loading"
    : error !== null ? "error" : shift === null ? "closed" : "ready";

  const closeCurrentDialog = useCallback(() => {
    setIsCloseDialogVisible(false);
    window.setTimeout(() => { closeTriggerRef.current?.focus(); }, 0);
  }, []);

  const shiftClosed = async (result: CashShiftCloseResponse) => {
    setIsCloseDialogVisible(false);
    await Promise.all([
      loadCurrent(),
      apiClient.GET("/api/v1/finance/operations").catch(() => null),
    ]);
    await navigate(`/finance/shifts?shift=${encodeURIComponent(result.shift.id)}`, {
      state: {
        financeFlash: result.replayed
          ? `Зміну ${result.shift.public_number} вже було закрито.`
          : `Касову зміну ${result.shift.public_number} закрито.`,
      },
    });
  };

  return (
    <>
      <header className="page-heading finance-heading">
        <div><p className="eyebrow">Фінанси · TP-704</p><h1>Оплати та каса</h1><p>Повні оплати й повернення, службові рухи готівки та поточна касова зміна.</p></div>
      </header>

      <FinanceSubnav />

      {success === null ? null : <div className="success-banner finance-success" role="status"><Icon name="check" /><span>{success}</span></div>}

      {isLoading ? <div aria-label="Завантаження поточної касової зміни" className="finance-loading" role="status"><span /><span /><span /></div> : null}
      {!isLoading && error !== null ? <section className="panel finance-state finance-state--error" role="alert"><Icon name="warning" /><div><h2>Не вдалося завантажити касову зміну</h2><p>{error}</p></div><button className="button button--secondary" onClick={() => { void loadCurrent(); }} type="button"><Icon name="refresh" />Повторити</button></section> : null}
      {!isLoading && error === null && shift === null ? <section className="panel finance-state finance-state--empty" aria-labelledby="finance-no-shift-title"><span className="finance-state__icon"><Icon name="finance" /></span><div><p className="eyebrow">Початок робочого дня</p><h2 id="finance-no-shift-title">Касову зміну ще не відкрито</h2><p>Перед першою фінансовою операцією відкрийте власну зміну. Початковий залишок автоматично дорівнює нулю.</p></div><button className="button button--primary" onClick={(event) => { openTriggerRef.current = event.currentTarget; setOpenError(null); setIsOpenDialogVisible(true); }} ref={openTriggerRef} type="button"><Icon name="plus" />Відкрити касову зміну</button></section> : null}
      {!isLoading && error === null && shift !== null ? <ShiftSummary closeTriggerRef={closeTriggerRef} headingRef={shiftHeadingRef} onCloseShift={() => { setIsCloseDialogVisible(true); }} shift={shift} /> : null}

      <FinanceOperations
        availableCashMinor={cashActionState === "ready" ? shift?.totals.expected_cash_minor ?? 0 : 0}
        cashActionState={cashActionState}
        onOperationSuccess={(message) => { setSuccess(message); }}
        refreshShift={loadCurrent}
      />

      {isOpenDialogVisible ? <OpenShiftDialog error={openError} isOpening={isOpening} onClose={closeDialog} onConfirm={() => { void openShift(); }} /> : null}
      {isCloseDialogVisible && shift !== null ? <CloseCashShiftDialog onClose={closeCurrentDialog} onSuccess={shiftClosed} shiftId={shift.id} shiftNumber={shift.public_number} /> : null}
    </>
  );
}
