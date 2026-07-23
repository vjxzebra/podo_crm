import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { sessionAwareFetch } from "../api/client";
import { attachmentFilename, downloadBlob, responseErrorMessage } from "../api/download";
import type { operations } from "../api/schema";
import { Icon } from "../app/Icon";
import { getAnalytics, type AnalyticsKpi, type AnalyticsResponse } from "./analyticsApi";

type PeriodPreset = "month" | "quarter" | "year" | "custom";
type AnalyticsExportQuery = NonNullable<operations["analytics_export"]["parameters"]["query"]>;

const moneyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
  maximumFractionDigits: 0,
});
const integerFormatter = new Intl.NumberFormat("uk-UA");
const shortDateFormatter = new Intl.DateTimeFormat("uk-UA", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Europe/Kyiv",
});

function clinicToday(): string {
  return new Intl.DateTimeFormat("en-CA", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Europe/Kyiv",
    year: "numeric",
  }).format(new Date());
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function isoDate(year: number, month: number, day: number): string {
  return `${String(year)}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function presetRange(preset: Exclude<PeriodPreset, "custom">, today: string) {
  const [year = 0, month = 0] = today.split("-").map(Number);
  if (preset === "year") return { from: isoDate(year, 1, 1), to: isoDate(year, 12, 31) };
  if (preset === "quarter") {
    const firstMonth = Math.floor((month - 1) / 3) * 3 + 1;
    const finalMonth = firstMonth + 2;
    return {
      from: isoDate(year, firstMonth, 1),
      to: isoDate(year, finalMonth, daysInMonth(year, finalMonth)),
    };
  }
  return {
    from: isoDate(year, month, 1),
    to: isoDate(year, month, daysInMonth(year, month)),
  };
}

function money(value: number): string {
  return moneyFormatter.format(value / 100);
}

function percent(basisPoints: number): string {
  return `${new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 1 }).format(basisPoints / 100)}%`;
}

function dateLabel(value: string): string {
  return shortDateFormatter.format(new Date(`${value}T12:00:00Z`));
}

function analyticsExportUrl(analytics: AnalyticsResponse): string {
  const url = new URL("/api/v1/analytics/export", window.location.origin);
  const query: AnalyticsExportQuery = {
    from: analytics.period.date_from,
    to: analytics.period.date_to,
    ...(analytics.filters.specialist === null
      ? {}
      : { specialist_id: Number(analytics.filters.specialist.id) }),
    ...(analytics.filters.service === null
      ? {}
      : { service_id: analytics.filters.service.id }),
  };
  Object.entries(query).forEach(([name, value]) => {
    url.searchParams.set(name, String(value));
  });
  return url.toString();
}

function kpiCards(kpis: AnalyticsKpi) {
  return [
    { key: "completed", label: "Завершені візити", value: integerFormatter.format(kpis.completed_visits), note: "клінічно завершені" },
    { key: "revenue", label: "Чистий виторг", value: money(kpis.revenue_minor), note: `${String(kpis.payment_count)} оплат · з урахуванням повернень` },
    { key: "average", label: "Середній чек", value: money(kpis.average_check_minor), note: "чистий виторг / оплати" },
    { key: "returning", label: "Повторні пацієнти", value: percent(kpis.returning_patient_rate_bps), note: `${String(kpis.returning_patients)} із ${String(kpis.served_patients)}` },
    { key: "new", label: "Нові пацієнти", value: integerFormatter.format(kpis.new_patients), note: "створені й обслужені у періоді" },
    { key: "interval", label: "Інтервал повернення", value: kpis.average_return_interval_days === null ? "—" : `${String(kpis.average_return_interval_days)} дн.`, note: "середнє між завершеними візитами" },
  ] as const;
}

function AnalyticsLoading() {
  return (
    <div className="analytics-loading" aria-label="Завантаження аналітики" role="progressbar">
      <span /><span /><span /><span /><span /><span />
    </div>
  );
}

export function AnalyticsPage() {
  const today = useMemo(clinicToday, []);
  const initialRange = useMemo(() => presetRange("month", today), [today]);
  const [preset, setPreset] = useState<PeriodPreset>("month");
  const [dateFrom, setDateFrom] = useState(initialRange.from);
  const [dateTo, setDateTo] = useState(initialRange.to);
  const [specialistId, setSpecialistId] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const rangeInvalid = dateFrom === "" || dateTo === "" || dateFrom > dateTo;

  useEffect(() => {
    if (rangeInvalid) return;
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    setExportError(null);
    setExportStatus(null);
    void getAnalytics(
      {
        dateFrom,
        dateTo,
        ...(specialistId === "" ? {} : { specialistId: Number(specialistId) }),
        ...(serviceId === "" ? {} : { serviceId }),
      },
      controller.signal,
    )
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.ok) {
          setError(result.error.message || "Не вдалося сформувати аналітику.");
          setAnalytics(null);
          return;
        }
        setAnalytics(result.data);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError("Немає зв’язку із сервером. Спробуйте ще раз.");
        setAnalytics(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => { controller.abort(); };
  }, [dateFrom, dateTo, rangeInvalid, reloadKey, serviceId, specialistId]);

  function applyPreset(nextPreset: Exclude<PeriodPreset, "custom">) {
    const range = presetRange(nextPreset, today);
    setPreset(nextPreset);
    setDateFrom(range.from);
    setDateTo(range.to);
  }

  async function exportAnalytics() {
    if (analytics === null || isLoading || error !== null || rangeInvalid) return;
    setIsExporting(true);
    setExportError(null);
    setExportStatus(null);
    const response = await sessionAwareFetch(new Request(analyticsExportUrl(analytics), {
      headers: { Accept: "text/csv" },
    })).catch(() => null);
    setIsExporting(false);
    if (response === null) {
      setExportError("Немає зв’язку із сервером. Не вдалося підготувати CSV аналітики.");
      return;
    }
    if (!response.ok) {
      setExportError(await responseErrorMessage(
        response,
        "Не вдалося підготувати CSV аналітики. Спробуйте ще раз.",
      ));
      return;
    }
    const blob = await response.blob();
    downloadBlob(blob, attachmentFilename(
      response.headers.get("Content-Disposition"),
      "analytics-report.csv",
    ));
    setExportStatus("Завантаження CSV аналітики розпочато.");
  }

  const maxTrendVisits = Math.max(1, ...(analytics?.trend.map((point) => point.visits) ?? []));
  const maxOutcome = Math.max(1, ...(analytics?.appointment_outcomes.map((item) => item.count) ?? []));

  return (
    <>
      <header className="page-heading analytics-heading">
        <div>
          <p className="eyebrow">Адміністрування · Єдині операційні правила</p>
          <h1>Аналітика клініки</h1>
          <p>Візити, виторг і завантаженість звіряються із незмінними клінічними та касовими фактами.</p>
        </div>
        <div className="analytics-heading__actions">
          <span className="analytics-heading__ledger"><Icon name="lock" /> Ledger-звірено</span>
          <button
            className="button button--secondary"
            disabled={isExporting || isLoading || error !== null || analytics === null || rangeInvalid}
            onClick={() => { void exportAnalytics(); }}
            type="button"
          >
            {isExporting ? "Готуємо CSV…" : "Експортувати CSV"}
          </button>
        </div>
      </header>

      {exportError === null ? null : <div className="form-message form-message--error analytics-export-message" role="alert"><Icon name="warning" /><span>{exportError}</span><button className="text-action" onClick={() => { void exportAnalytics(); }} type="button">Повторити export</button></div>}
      {exportStatus === null ? null : <div className="form-message form-message--success analytics-export-message" role="status"><Icon name="check" /><span>{exportStatus}</span></div>}

      <section className="panel analytics-filters" aria-labelledby="analytics-filters-heading">
        <header>
          <div><p className="eyebrow">Фільтри</p><h2 id="analytics-filters-heading">Період і зріз даних</h2></div>
          <span>{dateLabel(dateFrom)} — {dateLabel(dateTo)}</span>
        </header>
        <div className="analytics-periods" role="group" aria-label="Швидкий вибір періоду">
          {(["month", "quarter", "year"] as const).map((item) => (
            <button
              aria-pressed={preset === item}
              className={preset === item ? "is-active" : ""}
              key={item}
              type="button"
              onClick={() => { applyPreset(item); }}
            >
              {{ month: "Місяць", quarter: "Квартал", year: "Рік" }[item]}
            </button>
          ))}
          <button
            aria-pressed={preset === "custom"}
            className={preset === "custom" ? "is-active" : ""}
            type="button"
            onClick={() => { setPreset("custom"); }}
          >
            Свій період
          </button>
        </div>
        <div className="analytics-filter-grid">
          <label className="form-field">
            <span>Від</span>
            <input type="date" value={dateFrom} onChange={(event) => { setPreset("custom"); setDateFrom(event.target.value); }} />
          </label>
          <label className="form-field">
            <span>До</span>
            <input aria-invalid={rangeInvalid} type="date" value={dateTo} onChange={(event) => { setPreset("custom"); setDateTo(event.target.value); }} />
          </label>
          <label className="form-field">
            <span>Спеціаліст</span>
            <select value={specialistId} onChange={(event) => { setSpecialistId(event.target.value); }}>
              <option value="">Усі спеціалісти</option>
              {analytics?.available_specialists.map((item) => (
                <option value={item.id} key={item.id}>{item.name}{item.is_active ? "" : " · неактивний"}</option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Послуга</span>
            <select value={serviceId} onChange={(event) => { setServiceId(event.target.value); }}>
              <option value="">Усі послуги</option>
              {analytics?.available_services.map((item) => (
                <option value={item.id} key={item.id}>{item.name}{item.is_active ? "" : " · неактивна"}</option>
              ))}
            </select>
          </label>
        </div>
        {rangeInvalid ? <p className="form-message form-message--error" role="alert">Кінцева дата має бути не раніше за початкову.</p> : null}
      </section>

      {isLoading && !rangeInvalid ? <AnalyticsLoading /> : null}
      {!isLoading && error !== null ? (
        <section className="panel analytics-state" role="alert">
          <Icon name="warning" />
          <h2>Аналітика не сформована</h2>
          <p>{error}</p>
          <button className="button button--secondary" type="button" onClick={() => { setReloadKey((key) => key + 1); }}>
            <Icon name="refresh" />Повторити
          </button>
        </section>
      ) : null}

      {!isLoading && error === null && !rangeInvalid && analytics !== null ? (
        <>
          <section className="analytics-kpis" aria-label="Ключові показники аналітики">
            {kpiCards(analytics.kpis).map((item, index) => (
              <article className="analytics-kpi" key={item.key}>
                <span className={`analytics-kpi__marker analytics-kpi__marker--${String((index % 4) + 1)}`} aria-hidden="true" />
                <small>{item.label}</small>
                <strong>{item.value}</strong>
                <span>{item.note}</span>
              </article>
            ))}
          </section>

          <div className="analytics-main-grid">
            <section className="panel analytics-trend" aria-labelledby="analytics-trend-heading">
              <header className="panel__heading">
                <div><p className="eyebrow">Динаміка</p><h2 id="analytics-trend-heading">Візити та чистий виторг</h2><p>Періодизація: {analytics.period.bucket === "day" ? "за днями" : analytics.period.bucket === "week" ? "за тижнями" : "за місяцями"}</p></div>
              </header>
              {analytics.trend.every((point) => point.visits === 0 && point.revenue_minor === 0) ? (
                <div className="overview-empty"><Icon name="analytics" /><p><strong>Даних за період немає</strong><span>Змініть період або фільтри.</span></p></div>
              ) : (
                <div
                  aria-label="Графік завершених візитів і виторгу"
                  className="analytics-trend__chart"
                  role="region"
                  tabIndex={0}
                >
                  {analytics.trend.map((point) => (
                    <article key={point.date_from}>
                      <div className="analytics-trend__bar-zone">
                        <span
                          style={{ "--trend-height": `${String(Math.max(4, point.visits / maxTrendVisits * 100))}%` } as CSSProperties}
                          title={`${String(point.visits)} візитів`}
                        />
                      </div>
                      <strong>{point.visits}</strong>
                      <small>{point.label}</small>
                      <b>{money(point.revenue_minor)}</b>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="panel analytics-outcomes" aria-labelledby="analytics-outcomes-heading">
              <header className="panel__heading"><div><p className="eyebrow">Результати записів</p><h2 id="analytics-outcomes-heading">Статуси за період</h2></div></header>
              <div className="analytics-outcome-list">
                {analytics.appointment_outcomes.map((item) => (
                  <div key={item.code}>
                    <span><strong>{item.label}</strong><b>{item.count}</b></span>
                    <i><span style={{ width: `${String(item.count / maxOutcome * 100)}%` }} /></i>
                  </div>
                ))}
              </div>
              <dl className="analytics-outcome-summary">
                <div><dt>Скасування</dt><dd>{analytics.kpis.canceled_appointments}</dd></div>
                <div><dt>Неявки</dt><dd>{analytics.kpis.no_show_appointments}</dd></div>
              </dl>
            </section>
          </div>

          <section className="panel analytics-table-panel" aria-labelledby="specialist-performance-heading">
            <header className="panel__heading"><div><p className="eyebrow">Команда</p><h2 id="specialist-performance-heading">Завантаженість спеціалістів</h2><p>Заплановані хвилини / доступні хвилини клініки без перерв</p></div></header>
            {analytics.specialist_performance.length === 0 ? (
              <div className="overview-empty overview-empty--compact"><Icon name="team" /><p><strong>Активності немає</strong><span>У вибраному зрізі спеціалісти не мали записів або виторгу.</span></p></div>
            ) : (
              <div
                aria-label="Таблиця завантаженості спеціалістів"
                className="analytics-table-wrap"
                role="region"
                tabIndex={0}
              >
                <table>
                  <thead><tr><th scope="col">Спеціаліст</th><th scope="col">Візити</th><th scope="col">Заплановано</th><th scope="col">Завантаженість</th><th scope="col">Виторг</th></tr></thead>
                  <tbody>
                    {analytics.specialist_performance.map((item) => (
                      <tr key={item.id}>
                        <th scope="row">{item.name}{item.is_active ? "" : <small>Неактивний</small>}</th>
                        <td>{item.completed_visits}</td>
                        <td>{item.scheduled_minutes} / {item.available_minutes} хв</td>
                        <td><span className="utilization"><i><span style={{ width: `${String(item.utilization_bps / 100)}%` }} /></i><b>{percent(item.utilization_bps)}</b></span></td>
                        <td>{money(item.revenue_minor)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="panel analytics-table-panel" aria-labelledby="service-ranking-heading">
            <header className="panel__heading"><div><p className="eyebrow">Послуги</p><h2 id="service-ranking-heading">Рейтинг за виконаним обсягом</h2><p>Snapshot-рядки завершених візитів; поточна ціна каталогу не підміняє історію</p></div></header>
            {analytics.service_ranking.length === 0 ? (
              <div className="overview-empty overview-empty--compact"><Icon name="empty" /><p><strong>Послуг у зрізі немає</strong><span>Завершені візити за обраними фільтрами відсутні.</span></p></div>
            ) : (
              <div
                aria-label="Таблиця рейтингу послуг"
                className="analytics-table-wrap"
                role="region"
                tabIndex={0}
              >
                <table>
                  <thead><tr><th scope="col">#</th><th scope="col">Послуга</th><th scope="col">Візити</th><th scope="col">Кількість</th><th scope="col">Нараховано</th></tr></thead>
                  <tbody>
                    {analytics.service_ranking.map((item, index) => (
                      <tr key={item.id}>
                        <td><span className="ranking-number">{index + 1}</span></td>
                        <th scope="row">{item.name}<small>{item.code}</small></th>
                        <td>{item.visit_count}</td>
                        <td>{item.quantity}</td>
                        <td>{money(item.billed_total_minor)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </>
  );
}
