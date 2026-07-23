import { useCallback, useEffect, useState } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";

export type PatientHistoryItem =
  | components["schemas"]["PatientHistoryBaseItem"]
  | components["schemas"]["PatientHistoryMedicalItem"];

const visitDateFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const moneyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
  maximumFractionDigits: 2,
});

export function formatPatientVisitDate(value: string): string {
  return visitDateFormatter.format(new Date(value));
}

function money(minor: number): string {
  return moneyFormatter.format(minor / 100);
}

function isMedicalHistoryItem(
  visit: PatientHistoryItem,
): visit is components["schemas"]["PatientHistoryMedicalItem"] {
  return "clinical_summary" in visit;
}

function HistoryLoading() {
  return (
    <div aria-label="Завантаження історії візитів" className="patient-archive-loading" role="status">
      <span />
      <span />
      <span />
    </div>
  );
}

export function PatientVisitHistoryTab({ patientId }: { readonly patientId: string }) {
  const [visits, setVisits] = useState<readonly PatientHistoryItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (cursor: string | null = null) => {
    if (cursor === null) setIsLoading(true);
    else setIsLoadingMore(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/patients/{patient_id}/visits", {
      params: {
        path: { patient_id: patientId },
        ...(cursor === null ? {} : { query: { cursor } }),
      },
    }).catch(() => null);
    setIsLoading(false);
    setIsLoadingMore(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Історія лишилася без змін.");
      return;
    }
    if (result.data === undefined) {
      setError(result.error.message);
      return;
    }
    const page = result.data.visits as readonly PatientHistoryItem[];
    setVisits((current) => cursor === null ? page : [...current, ...page]);
    setNextCursor(result.data.next_cursor);
  }, [patientId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="surface patient-archive" aria-labelledby="patient-history-title">
      <header className="patient-archive__header">
        <div>
          <p className="eyebrow">Завершені прийоми</p>
          <h2 id="patient-history-title">Історія візитів</h2>
          <p>Хронологія сформована із зафіксованих snapshot-даних кожного прийому.</p>
        </div>
        <span className="patient-privacy-badge"><Icon name="lock" />Доступ за роллю</span>
      </header>

      {isLoading ? <HistoryLoading /> : null}
      {!isLoading && error !== null && visits.length === 0 ? (
        <div className="patient-archive-state" role="alert">
          <Icon name="warning" />
          <div><strong>Не вдалося завантажити історію</strong><p>{error}</p></div>
          <button className="button button--secondary" onClick={() => { void load(); }} type="button"><Icon name="refresh" />Повторити</button>
        </div>
      ) : null}
      {!isLoading && error === null && visits.length === 0 ? (
        <div className="patient-archive-state patient-archive-state--empty">
          <Icon name="calendar" />
          <div><strong>Завершених візитів ще немає</strong><p>Перший запис з’явиться тут одразу після завершення прийому.</p></div>
        </div>
      ) : null}

      {visits.length > 0 ? (
        <div className="patient-history-list">
          {visits.map((visit) => {
            const medical = isMedicalHistoryItem(visit);
            return (
              <article className="patient-history-card" key={visit.id}>
                <div className="patient-history-card__rail" aria-hidden="true"><span /></div>
                <div className="patient-history-card__body">
                  <header>
                    <div>
                      <time dateTime={visit.occurred_at}>{formatPatientVisitDate(visit.occurred_at)}</time>
                      <h3>{visit.services.map((service) => service.service_name).join(" · ") || "Послуги не зазначені"}</h3>
                      <p>{visit.public_number} · {visit.specialist.display_name}</p>
                    </div>
                    <div className="patient-history-card__totals">
                      <span>{visit.status_label}</span>
                      <strong>{money(visit.total_minor)}</strong>
                    </div>
                  </header>
                  {medical && visit.clinical_summary.trim() !== "" ? (
                    <p className="patient-history-card__summary">{visit.clinical_summary}</p>
                  ) : null}
                  {medical ? (
                    <div className="patient-history-card__markers" aria-label="Медичні матеріали візиту">
                      <span className={visit.has_photos ? "available" : ""}><Icon name="photo" />До {visit.before_photo_count} · Після {visit.after_photo_count}</span>
                      <span className={visit.recommendations_count > 0 ? "available" : ""}><Icon name="tasks" />Рекомендацій: {visit.recommendations_count}</span>
                    </div>
                  ) : null}
                  <details className="patient-history-details">
                    <summary>Деталі візиту</summary>
                    <dl>
                      <div><dt>Завершено</dt><dd>{formatPatientVisitDate(visit.completed_at)}</dd></div>
                      <div><dt>Спеціаліст</dt><dd>{visit.specialist.display_name}</dd></div>
                      {visit.services.map((service, index) => (
                        <div key={`${visit.id}-${String(index)}`}>
                          <dt>{service.service_name}</dt>
                          <dd>{service.quantity} × {money(service.line_total_minor / service.quantity)}</dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}

      {error !== null && visits.length > 0 ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
      {nextCursor === null ? null : (
        <div className="patient-archive__more">
          <button className="button button--secondary" disabled={isLoadingMore} onClick={() => { void load(nextCursor); }} type="button">
            {isLoadingMore ? "Завантажуємо…" : "Показати попередні візити"}
          </button>
        </div>
      )}
    </section>
  );
}
