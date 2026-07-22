import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { Link } from "react-router";

import { Icon, type IconName } from "../app/Icon";
import { OverviewWorkItems } from "../work-items/OverviewWorkItems";
import {
  getOverview,
  type OverviewAppointment,
  type OverviewMetric,
  type OverviewResponse,
} from "./analyticsApi";

const moneyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
  maximumFractionDigits: 0,
});
const dateFormatter = new Intl.DateTimeFormat("uk-UA", {
  day: "numeric",
  month: "long",
  weekday: "long",
  timeZone: "Europe/Kyiv",
});
const timeFormatter = new Intl.DateTimeFormat("uk-UA", {
  hour: "2-digit",
  minute: "2-digit",
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

function moveDate(value: string, days: number): string {
  const [year = 0, month = 0, day = 0] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

function formatLocalDate(value: string): string {
  return dateFormatter.format(new Date(`${value}T12:00:00Z`));
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toLocaleUpperCase("uk-UA");
}

function metricIcon(key: string): IconName {
  if (key.includes("payment") || key.includes("income")) return "finance";
  if (key === "patients" || key === "specialists") return "patients";
  if (key === "workday_minutes") return "analytics";
  if (key === "attention" || key === "unpaid_visits") return "bell";
  return "calendar";
}

function metricValue(metric: OverviewMetric): string {
  if (metric.format === "money") return moneyFormatter.format(metric.value / 100);
  if (metric.format === "duration") {
    const hours = Math.floor(metric.value / 60);
    const minutes = metric.value % 60;
    return `${String(hours)} год${minutes === 0 ? "" : ` ${String(minutes)} хв`}`;
  }
  return new Intl.NumberFormat("uk-UA").format(metric.value);
}

function appointmentStyle(appointment: OverviewAppointment): CSSProperties {
  return { "--appointment-color": appointment.service.color } as CSSProperties;
}

function OverviewAppointmentRow({ appointment }: { readonly appointment: OverviewAppointment }) {
  return (
    <article className="timeline-item">
      <time dateTime={appointment.starts_at}>{timeFormatter.format(new Date(appointment.starts_at))}</time>
      <span className="timeline-item__rail" aria-hidden="true" />
      <Link
        className="appointment-card overview-appointment"
        style={appointmentStyle(appointment)}
        to={`/calendar?appointment=${appointment.id}`}
      >
        <span className="avatar avatar--sage" aria-hidden="true">
          {initials(appointment.patient.display_name)}
        </span>
        <span>
          <strong>{appointment.patient.display_name}</strong>
          <small>
            {appointment.service.name} · {appointment.duration_minutes} хв · {appointment.room.name}
          </small>
          <small>{appointment.specialist.display_name}</small>
        </span>
        <span className="status-pill" style={{ borderColor: appointment.status.color }}>
          {appointment.status.label}
        </span>
      </Link>
    </article>
  );
}

function OverviewLoading() {
  return (
    <div className="overview-loading" aria-label="Завантаження операційного огляду" role="progressbar">
      <span /><span /><span /><span />
    </div>
  );
}

export function OverviewPage() {
  const today = useMemo(clinicToday, []);
  const [selectedDate, setSelectedDate] = useState(today);
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    void getOverview(selectedDate, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.ok) {
          setError(result.error.message || "Не вдалося завантажити операційний огляд.");
          setOverview(null);
          return;
        }
        setOverview(result.data);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError("Немає зв’язку із сервером. Спробуйте ще раз.");
        setOverview(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => { controller.abort(); };
  }, [selectedDate, reloadKey]);

  return (
    <>
      <header className="page-heading overview-heading">
        <div>
          <p className="eyebrow">{formatLocalDate(selectedDate)} · Операційний огляд</p>
          <h1>Добрий день</h1>
          <p>Розклад, показники та справи сформовано з актуальних даних клініки.</p>
        </div>
        <div className="date-switcher" aria-label="Навігація за датою">
          <button
            type="button"
            aria-label="Попередній день"
            onClick={() => { setSelectedDate((value) => moveDate(value, -1)); }}
          >
            <Icon name="arrow-left" />
          </button>
          <button
            className="date-switcher__current"
            type="button"
            onClick={() => { setSelectedDate(today); }}
          >
            {selectedDate === today ? "Сьогодні" : formatLocalDate(selectedDate).replace(/^\S+,\s*/u, "")}
          </button>
          <button
            type="button"
            aria-label="Наступний день"
            onClick={() => { setSelectedDate((value) => moveDate(value, 1)); }}
          >
            <Icon name="chevron" />
          </button>
        </div>
      </header>

      {isLoading ? <OverviewLoading /> : null}
      {!isLoading && error !== null ? (
        <section className="panel overview-state" role="alert">
          <Icon name="warning" />
          <h2>Огляд не завантажився</h2>
          <p>{error}</p>
          <button className="button button--secondary" type="button" onClick={() => { setReloadKey((key) => key + 1); }}>
            <Icon name="refresh" />Повторити
          </button>
        </section>
      ) : null}

      {!isLoading && error === null && overview !== null ? (
        <>
          <section className="stats-grid" aria-label="Ключові показники">
            {overview.metrics.map((metric) => (
              <article className="stat-card" key={metric.key}>
                <span className={`stat-card__icon stat-card__icon--${metric.tone}`}>
                  <Icon name={metricIcon(metric.key)} />
                </span>
                <span className="stat-card__copy">
                  <small>{metric.label}</small>
                  <strong>{metricValue(metric)}</strong>
                  <span>{metric.note}</span>
                </span>
              </article>
            ))}
          </section>

          <div className="dashboard-grid">
            <section className="panel schedule-panel" aria-labelledby="overview-schedule-heading">
              <header className="panel__heading">
                <div>
                  <p className="eyebrow">Розклад</p>
                  <h2 id="overview-schedule-heading">Записи на день</h2>
                  <p>{overview.schedule.length} активних записів · Europe/Kyiv</p>
                </div>
                <Link className="text-link" to="/calendar">
                  Увесь календар <Icon name="chevron" />
                </Link>
              </header>
              {overview.schedule.length === 0 ? (
                <div className="overview-empty">
                  <Icon name="calendar" />
                  <p><strong>Записів немає</strong><span>Для цієї дати активний розклад порожній.</span></p>
                </div>
              ) : (
                <div className="timeline">
                  {overview.schedule.map((appointment) => (
                    <OverviewAppointmentRow appointment={appointment} key={appointment.id} />
                  ))}
                </div>
              )}
            </section>

            <div className="dashboard-side">
              <section className="panel next-patient" aria-labelledby="next-patient-heading">
                <header className="panel__heading">
                  <div>
                    <p className="eyebrow"><span className="live-dot" /> Наступний запис</p>
                    <h2 id="next-patient-heading">
                      {overview.next_appointment === null
                        ? "На цю дату більше немає"
                        : timeFormatter.format(new Date(overview.next_appointment.starts_at))}
                    </h2>
                  </div>
                  {overview.next_appointment === null ? null : (
                    <span className="status-pill">{overview.next_appointment.status.label}</span>
                  )}
                </header>
                {overview.next_appointment === null ? (
                  <div className="overview-empty overview-empty--compact">
                    <Icon name="check" />
                    <p><strong>Розклад опрацьовано</strong><span>Оберіть іншу дату або відкрийте календар.</span></p>
                  </div>
                ) : (
                  <>
                    <div className="patient-hero">
                      <span className="avatar avatar--large avatar--lilac" aria-hidden="true">
                        {initials(overview.next_appointment.patient.display_name)}
                      </span>
                      <span>
                        <strong>{overview.next_appointment.patient.display_name}</strong>
                        <small>{overview.next_appointment.service.name}</small>
                      </span>
                    </div>
                    <dl className="patient-facts">
                      <div><dt>Час</dt><dd>{timeFormatter.format(new Date(overview.next_appointment.starts_at))}</dd></div>
                      <div><dt>Тривалість</dt><dd>{overview.next_appointment.duration_minutes} хв</dd></div>
                      <div><dt>Кабінет</dt><dd>{overview.next_appointment.room.name}</dd></div>
                    </dl>
                    <Link className="button button--secondary button--full" to={`/calendar?appointment=${overview.next_appointment.id}`}>
                      Відкрити запис
                    </Link>
                  </>
                )}
              </section>

              <section className="panel overview-attention" aria-labelledby="overview-attention-heading">
                <header className="panel__heading">
                  <div><p className="eyebrow">Контроль</p><h2 id="overview-attention-heading">Потребує уваги</h2></div>
                </header>
                {overview.attention.every((item) => item.count === 0) ? (
                  <div className="overview-empty overview-empty--compact">
                    <Icon name="check" />
                    <p><strong>Усе під контролем</strong><span>Критичних справ на цю мить немає.</span></p>
                  </div>
                ) : (
                  <div className="attention-list">
                    {overview.attention.filter((item) => item.count > 0).map((item) => (
                      <Link to={item.deep_link} key={item.kind}>
                        <span>{item.label}</span><strong>{item.count}</strong><Icon name="chevron" />
                      </Link>
                    ))}
                  </div>
                )}
              </section>

              <OverviewWorkItems />
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
