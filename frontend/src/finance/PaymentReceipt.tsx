import { useRef, useState } from "react";

import { sessionAwareFetch } from "../api/client";
import { attachmentFilename, downloadBlob, responseErrorMessage } from "../api/download";
import { Icon } from "../app/Icon";
import { useFinanceDialogLifecycle } from "./dialogLifecycle";
import { money } from "./financeFormat";
import type { FinancePaymentOperation } from "./financeTypes";

function receiptUrl(paymentId: string, disposition: "attachment" | "inline"): string {
  const url = new URL(`/api/v1/payments/${paymentId}/receipt`, window.location.origin);
  url.searchParams.set("disposition", disposition);
  return url.toString();
}

async function fetchReceipt(
  paymentId: string,
  disposition: "attachment" | "inline",
): Promise<Response> {
  const response = await sessionAwareFetch(new Request(
    receiptUrl(paymentId, disposition),
    { headers: { Accept: "application/pdf" } },
  ));
  if (!response.ok) {
    throw new Error(await responseErrorMessage(
      response,
      "Не вдалося сформувати PDF квитанції.",
    ));
  }
  return response;
}

export function PaymentReceiptActions({
  paymentId,
  publicNumber,
}: {
  readonly paymentId: string;
  readonly publicNumber: string;
}) {
  const [activeAction, setActiveAction] = useState<"download" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const download = async () => {
    if (activeAction !== null) return;
    setActiveAction("download");
    setError(null);
    setStatus(null);
    try {
      const response = await fetchReceipt(paymentId, "attachment");
      downloadBlob(
        await response.blob(),
        attachmentFilename(
          response.headers.get("Content-Disposition"),
          `payment-receipt-${publicNumber}.pdf`,
        ),
      );
      setStatus("Завантаження PDF розпочато.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не вдалося завантажити квитанцію.");
    } finally {
      setActiveAction(null);
    }
  };

  return (
    <div className="finance-receipt-actions">
      <div className="finance-receipt-actions__buttons">
        <button
          aria-label={`Завантажити PDF квитанції ${publicNumber}`}
          className="button button--secondary"
          disabled={activeAction !== null}
          onClick={() => { void download(); }}
          type="button"
        >
          <Icon name="download" />
          {activeAction === "download" ? "Формуємо PDF…" : "Завантажити PDF"}
        </button>
        <a
          aria-label={`Відкрити PDF для друку ${publicNumber}`}
          className="button button--primary"
          href={receiptUrl(paymentId, "inline")}
          rel="noopener noreferrer"
          target="_blank"
        >
          <Icon name="print" />
          Відкрити для друку
        </a>
      </div>
      {error === null ? null : <p className="finance-receipt-actions__message finance-receipt-actions__message--error" role="alert">{error}</p>}
      {status === null ? null : <p className="finance-receipt-actions__message" role="status">{status}</p>}
    </div>
  );
}

export function PaymentReceiptDialog({
  onClose,
  operation,
}: {
  readonly onClose: () => void;
  readonly operation: FinancePaymentOperation;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useFinanceDialogLifecycle({ dialogRef, initialFocusRef: closeRef, onEscape: onClose });
  const payment = operation.payment;
  if (payment === null) return null;

  return (
    <div
      className="modal-layer finance-receipt-layer"
      onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}
      role="presentation"
    >
      <section
        aria-labelledby="finance-receipt-title"
        aria-modal="true"
        className="modal-card finance-receipt-dialog"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Оплату прийнято</p>
            <h2 id="finance-receipt-title">Квитанція готова</h2>
            <p>{payment.public_number} · {operation.patient.display_name}</p>
          </div>
          <button
            aria-label="Закрити готову квитанцію"
            className="icon-button"
            onClick={onClose}
            ref={closeRef}
            type="button"
          >
            <Icon name="close" />
          </button>
        </header>

        <div className="finance-receipt-dialog__summary">
          <span aria-hidden="true"><Icon name="check" /></span>
          <div>
            <small>Сплачено</small>
            <strong>{money(operation.amount_minor)}</strong>
            <p>PDF містить квитанцію про оплату та окремий бланк рекомендацій подолога.</p>
          </div>
        </div>

        <div className="finance-receipt-dialog__notice">
          <Icon name="info" />
          <p>Документ не є фіскальним чеком. Фіскальний чек формується окремо через РРО/ПРРО.</p>
        </div>

        <PaymentReceiptActions
          paymentId={payment.id}
          publicNumber={payment.public_number}
        />

        <footer className="modal-card__footer">
          <button className="button button--secondary" onClick={onClose} type="button">Готово</button>
        </footer>
      </section>
    </div>
  );
}
