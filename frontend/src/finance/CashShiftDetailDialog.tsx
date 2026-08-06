import { useRef, useState } from "react";

import { sessionAwareFetch } from "../api/client";
import { attachmentFilename, downloadBlob, responseErrorMessage } from "../api/download";
import { Icon } from "../app/Icon";
import { roleLabels } from "../auth/AuthContext";
import type { CashLedgerEntrySnapshot, CashShiftProjection } from "./cashShiftTypes";
import { useFinanceDialogLifecycle } from "./dialogLifecycle";
import { dateTimeFormatter, methodLabels, money } from "./financeFormat";

interface CashShiftDetailDialogProps {
  readonly shift: CashShiftProjection;
  readonly onClose: () => void;
  readonly onRequestClose?: () => void;
}

const kindLabels: Readonly<Record<CashLedgerEntrySnapshot["kind"], string>> = {
  PAYMENT: "Оплата",
  REFUND: "Повернення",
  DEPOSIT: "Внесення",
  WITHDRAWAL: "Вилучення",
};

function entryAmount(entry: CashLedgerEntrySnapshot): string {
  const outgoing = entry.kind === "REFUND" || entry.kind === "WITHDRAWAL";
  return `${outgoing ? "−" : "+"}${money(entry.amount_minor)}`;
}

export function CashShiftDetailDialog({ shift, onClose, onRequestClose }: CashShiftDetailDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  useFinanceDialogLifecycle({ dialogRef, initialFocusRef: closeRef, onEscape: onClose });
  const totals = shift.totals;
  const reconciliation = shift.reconciliation;
  const openingSource = shift.opening_source_shift === null
    ? shift.opening_basis === "LEGACY" ? "Історична зміна" : "Перша зміна каси"
    : shift.opening_source_shift.public_number;
  const exportShift = async () => {
    setIsExporting(true);
    setExportError(null);
    setExportStatus(null);
    const response = await sessionAwareFetch(new Request(
      new URL(`/api/v1/cash-shifts/${shift.id}/export`, window.location.origin),
      { headers: { Accept: "text/csv" } },
    )).catch(() => null);
    setIsExporting(false);
    if (response === null) {
      setExportError("Немає зв’язку із сервером. Не вдалося підготувати CSV зміни.");
      return;
    }
    if (!response.ok) {
      setExportError(await responseErrorMessage(
        response,
        "Не вдалося підготувати CSV зміни. Спробуйте ще раз.",
      ));
      return;
    }
    const blob = await response.blob();
    downloadBlob(blob, attachmentFilename(
      response.headers.get("Content-Disposition"),
      `cash-shift-${shift.public_number}.csv`,
    ));
    setExportStatus("Завантаження CSV зміни розпочато.");
  };

  return (
    <div className="modal-layer finance-shift-detail-layer" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }} role="presentation">
      <section aria-labelledby="finance-shift-detail-title" aria-modal="true" className="modal-card finance-shift-detail-dialog" ref={dialogRef} role="dialog" tabIndex={-1}>
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Касова зміна · {shift.status === "CLOSED" ? "Закрита" : "Відкрита"}</p>
            <h2 id="finance-shift-detail-title">{shift.public_number}</h2>
            <p>{shift.employee.name} · {dateTimeFormatter.format(new Date(shift.opened_at))}</p>
          </div>
          <button aria-label={`Закрити деталі ${shift.public_number}`} className="icon-button" onClick={onClose} ref={closeRef} type="button"><Icon name="close" /></button>
        </header>

        <div className="finance-shift-detail-scroll">
          <section aria-label="Статус і працівник" className="finance-shift-detail-hero">
            <span className={`finance-history-status finance-history-status--${shift.status.toLocaleLowerCase()}`}>{shift.status === "CLOSED" ? "Закрита" : "Відкрита"}</span>
            <div><small>Працівник</small><strong>{shift.employee.name}</strong><span>{roleLabels[shift.employee.role]} · {shift.employee.email}</span></div>
            <dl>
              <div><dt>Відкрито</dt><dd>{dateTimeFormatter.format(new Date(shift.opened_at))}</dd></div>
              <div><dt>Закрито</dt><dd>{shift.closed_at === null ? "—" : dateTimeFormatter.format(new Date(shift.closed_at))}</dd></div>
              <div><dt>Початковий залишок</dt><dd>{money(shift.opening_cash_minor)}</dd></div>
              <div><dt>Джерело залишку</dt><dd>{openingSource}</dd></div>
            </dl>
          </section>

          <section aria-labelledby="finance-shift-detail-totals" className="finance-shift-detail-section">
            <header><div><p className="eyebrow">Ledger-derived</p><h3 id="finance-shift-detail-totals">Фінансовий підсумок</h3></div><span>{totals.operations_count} операцій</span></header>
            <dl className="finance-shift-detail-totals">
              <div><dt>Виторг</dt><dd>{money(totals.revenue_minor)}</dd></div>
              <div><dt>Оплати</dt><dd>{money(totals.payments_total_minor)}</dd></div>
              <div><dt>Повернення</dt><dd>−{money(totals.refunds_total_minor)}</dd></div>
              <div><dt>Готівка</dt><dd>{money(totals.cash_payments_minor - totals.cash_refunds_minor)}</dd></div>
              <div><dt>Картка</dt><dd>{money(totals.card_payments_minor - totals.card_refunds_minor)}</dd></div>
              <div><dt>Переказ</dt><dd>{money(totals.transfer_payments_minor - totals.transfer_refunds_minor)}</dd></div>
              <div><dt>Внесення</dt><dd>+{money(totals.deposits_minor)}</dd></div>
              <div><dt>Вилучення</dt><dd>−{money(totals.withdrawals_minor)}</dd></div>
            </dl>
          </section>

          <section aria-labelledby="finance-shift-detail-reconciliation" className="finance-shift-detail-section finance-shift-detail-reconciliation">
            <header><div><p className="eyebrow">Фізична готівка</p><h3 id="finance-shift-detail-reconciliation">Звірка каси</h3></div></header>
            <dl>
              <div><dt>Очікувалось</dt><dd>{money(totals.expected_cash_minor)}</dd></div>
              <div><dt>Фактично</dt><dd>{reconciliation === null ? "—" : money(reconciliation.actual_cash_minor)}</dd></div>
              <div><dt>Розбіжність</dt><dd className={reconciliation !== null && reconciliation.discrepancy_minor !== 0 ? "finance-discrepancy-value" : undefined}>{reconciliation === null ? "—" : `${reconciliation.discrepancy_minor > 0 ? "+" : reconciliation.discrepancy_minor < 0 ? "−" : ""}${money(Math.abs(reconciliation.discrepancy_minor))}`}</dd></div>
            </dl>
            {reconciliation === null ? <p>Звірка з’явиться після закриття зміни.</p> : (
              <div className="finance-shift-close-meta">
                <div><span>Закрив зміну</span><strong>{reconciliation.closed_by.name}</strong><small>{roleLabels[reconciliation.closed_by.role]} · {reconciliation.closed_by.email}</small></div>
                <div><span>Коментар</span><p>{reconciliation.comment === "" ? "Без коментаря" : reconciliation.comment}</p></div>
              </div>
            )}
          </section>

          <section aria-labelledby="finance-shift-detail-ledger" className="finance-shift-detail-section finance-shift-detail-ledger">
            <header><div><p className="eyebrow">Append-only</p><h3 id="finance-shift-detail-ledger">Усі касові операції</h3></div><span>{shift.entries.length}</span></header>
            {shift.entries.length === 0 ? (
              <div className="finance-shift-detail-empty"><Icon name="empty" /><p>У цій зміні немає касових операцій.</p></div>
            ) : (
              <div aria-label={`Операції ${shift.public_number}`} className="finance-shift-detail-ledger-table" role="table">
                <div className="finance-shift-detail-ledger-head" role="row"><span role="columnheader">Дата / номер</span><span role="columnheader">Операція</span><span role="columnheader">Спосіб</span><span role="columnheader">Працівник</span><span role="columnheader">Сума</span></div>
                {shift.entries.map((entry) => {
                  const method = entry.payment_method === null ? "Не застосовується" : methodLabels[entry.payment_method];
                  const outgoing = entry.kind === "REFUND" || entry.kind === "WITHDRAWAL";
                  return (
                    <div className="finance-shift-detail-ledger-row" key={entry.id} role="row">
                      <span data-label="Дата / номер" role="cell"><strong>{dateTimeFormatter.format(new Date(entry.posted_at))}</strong><small>{entry.public_number}</small></span>
                      <span data-label="Операція" role="cell"><b className={`finance-ledger-kind finance-ledger-kind--${entry.kind.toLocaleLowerCase()}`}>{kindLabels[entry.kind]}</b></span>
                      <span data-label="Спосіб" role="cell">{method}</span>
                      <span data-label="Працівник" role="cell"><strong>{entry.actor_name}</strong><small>{entry.actor_email}</small></span>
                      <span className={outgoing ? "finance-ledger-amount finance-ledger-amount--out" : "finance-ledger-amount"} data-label="Сума" role="cell">{entryAmount(entry)}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        {exportError === null ? null : <div className="form-message form-message--error finance-shift-export-message" role="alert"><Icon name="warning" /><span>{exportError}</span><button className="text-action" onClick={() => { void exportShift(); }} type="button">Повторити export</button></div>}
        {exportStatus === null ? null : <div className="form-message form-message--success finance-shift-export-message" role="status"><Icon name="check" /><span>{exportStatus}</span></div>}

        <footer className="modal-card__footer finance-shift-detail-footer">
          <span><Icon name="lock" />{shift.status === "CLOSED" ? "Закриту зміну не можна редагувати, видалити або відкрити повторно." : "Ledger відкритої зміни незмінний; доступне лише закриття зі звіркою."}</span>
          <div>
            <button className="button button--secondary" disabled={isExporting} onClick={() => { void exportShift(); }} type="button">{isExporting ? "Готуємо CSV…" : "Експортувати CSV"}</button>
            <button className="button button--secondary" onClick={onClose} type="button">Готово</button>
            {shift.status === "OPEN" && shift.permissions.can_close && onRequestClose !== undefined ? <button className="button button--danger" onClick={onRequestClose} type="button">Закрити зміну</button> : null}
          </div>
        </footer>
      </section>
    </div>
  );
}
