import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { useNavigate, useSearchParams } from "react-router";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { roleLabels, useAuth } from "../auth/AuthContext";
import { AppointmentCreateDialog, type SlotPreset } from "./AppointmentCreateDialog";
import { CalendarDatePicker } from "./CalendarDatePicker";
import { AppointmentDetailDialog } from "./AppointmentDetailDialog";

type CalendarResponse = components["schemas"]["CalendarResponse"];
type CalendarDay = components["schemas"]["CalendarDay"];
type CalendarEvent = components["schemas"]["CalendarEvent"];
type Specialist = components["schemas"]["SpecialistSummary"];
type CalendarView = "day" | "week";

const CLINIC_TIMEZONE = "Europe/Kyiv";
const SLOT_MINUTES = 15;
const minuteMs = 60_000;

const dateFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: CLINIC_TIMEZONE,
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

const shortDateFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: CLINIC_TIMEZONE,
  weekday: "short",
  day: "numeric",
  month: "short",
});

const timeFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: CLINIC_TIMEZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function dateKey(value: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: CLINIC_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  return `${pick("year")}-${pick("month")}-${pick("day")}`;
}

function parseDateKey(value: string): readonly [number, number, number] {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (match?.[1] === undefined || match[2] === undefined || match[3] === undefined) {
    throw new Error("Invalid calendar date key.");
  }
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function addDays(value: string, amount: number): string {
  const [year, month, day] = parseDateKey(value);
  return new Date(Date.UTC(year, month - 1, day + amount)).toISOString().slice(0, 10);
}

function startOfWeek(value: string): string {
  const [year, month, day] = parseDateKey(value);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  return addDays(value, -((weekday + 6) % 7));
}

function zonedMidnight(value: string): Date {
  const [year, month, day] = parseDateKey(value);
  const guess = new Date(Date.UTC(year, month - 1, day));
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: CLINIC_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(guess);
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((part) => part.type === type)?.value ?? 0);
  const renderedAsUtc = Date.UTC(
    pick("year"),
    pick("month") - 1,
    pick("day"),
    pick("hour"),
    pick("minute"),
    pick("second"),
  );
  return new Date(guess.getTime() - (renderedAsUtc - guess.getTime()));
}

function rangeFor(view: CalendarView, selectedDate: string) {
  const firstDate = view === "week" ? startOfWeek(selectedDate) : selectedDate;
  const lastDate = addDays(firstDate, view === "week" ? 7 : 1);
  return {
    from: zonedMidnight(firstDate).toISOString(),
    to: zonedMidnight(lastDate).toISOString(),
  };
}

function timeLabel(value: string): string {
  return timeFormatter.format(new Date(value));
}

function intervalOverlaps(
  start: number,
  end: number,
  otherStart: number,
  otherEnd: number,
): boolean {
  return start < otherEnd && end > otherStart;
}

function minutesBetween(start: string, end: string): number {
  return Math.round((new Date(end).getTime() - new Date(start).getTime()) / minuteMs);
}

function eventsForDay(events: readonly CalendarEvent[], day: CalendarDay): CalendarEvent[] {
  if (day.starts_at === null || day.ends_at === null) return [];
  const start = new Date(day.starts_at).getTime();
  const end = new Date(day.ends_at).getTime();
  return events.filter((event) => intervalOverlaps(
    new Date(event.starts_at).getTime(),
    new Date(event.ends_at).getTime(),
    start,
    end,
  ));
}

function CalendarLoading() {
  return (
    <section className="calendar-loading panel" aria-live="polite" aria-busy="true">
      <span className="spinner" aria-hidden="true" />
      <div>
        <h2>Завантажуємо розклад</h2>
        <p>Готуємо робочі години, перерви та записи команди…</p>
      </div>
    </section>
  );
}

function DayCalendar({
  day,
  events,
  onEventSelect,
  onSlotSelect,
  specialists,
}: {
  readonly day: CalendarDay | undefined;
  readonly events: readonly CalendarEvent[];
  readonly onEventSelect: (appointmentId: string) => void;
  readonly onSlotSelect: (preset: SlotPreset) => void;
  readonly specialists: readonly Specialist[];
}) {
  if (day === undefined || !day.is_working || day.starts_at === null || day.ends_at === null) {
    return (
      <section className="calendar-closed panel">
        <span className="calendar-closed__icon" aria-hidden="true"><Icon name="calendar" /></span>
        <h2>Клініка цього дня не працює</h2>
        <p>Робочий час і перерви задаються в єдиному графіку кабінету.</p>
      </section>
    );
  }
  if (specialists.length === 0) {
    return (
      <section className="calendar-closed panel">
        <span className="calendar-closed__icon" aria-hidden="true"><Icon name="team" /></span>
        <h2>Немає активних спеціалістів</h2>
        <p>Календар з’явиться після активації хоча б одного подолога.</p>
      </section>
    );
  }

  const dayStart = new Date(day.starts_at).getTime();
  const dayEnd = new Date(day.ends_at).getTime();
  const rowCount = Math.ceil((dayEnd - dayStart) / (SLOT_MINUTES * minuteMs));
  const visibleEvents = eventsForDay(events, day).filter((event) =>
    specialists.some((specialist) => specialist.id === event.specialist.id));
  const gridStyle = {
    "--calendar-rows": rowCount,
    gridTemplateColumns: `64px repeat(${String(specialists.length)}, minmax(190px, 1fr))`,
    minWidth: `${String(64 + specialists.length * 210)}px`,
  } as CSSProperties;

  return (
    <section className="calendar-day panel" aria-label="Денний календар">
      {visibleEvents.length === 0 ? (
        <div className="calendar-empty-note" role="status">
          <Icon name="calendar" />
          <span><strong>Записів цього дня немає</strong><small>Усі незаблоковані клітинки є вільними вікнами.</small></span>
        </div>
      ) : null}
      {specialists.length > 1 ? (
        <p className="calendar-scroll-hint" id="calendar-day-scroll-hint">
          <span aria-hidden="true">↔</span>
          Гортайте горизонтально; з клавіатури використовуйте стрілки.
        </p>
      ) : null}
      <div
        aria-describedby={specialists.length > 1 ? "calendar-day-scroll-hint" : undefined}
        aria-label="Прокручувана сітка спеціалістів"
        className="calendar-day__scroll"
        data-testid="calendar-day-scroll"
        tabIndex={0}
      >
        <div className="calendar-grid-header" style={gridStyle}>
          <span className="calendar-grid-header__time">Час</span>
          {specialists.map((specialist) => (
            <span className="calendar-specialist" key={specialist.id}>
              <span className="avatar avatar--sage" aria-hidden="true">
                {specialist.display_name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("")}
              </span>
              <span><strong>{specialist.display_name}</strong><small>Подолог</small></span>
            </span>
          ))}
        </div>
        <div className="calendar-grid" style={gridStyle}>
          {Array.from({ length: rowCount }, (_, row) => {
            const slotStart = dayStart + row * SLOT_MINUTES * minuteMs;
            return (
              <span
                className={`calendar-time ${row % 4 === 0 ? "calendar-time--hour" : ""}`}
                key={`time-${String(slotStart)}`}
                style={{ gridColumn: 1, gridRow: row + 1 }}
              >
                {row % 4 === 0 ? timeLabel(new Date(slotStart).toISOString()) : ""}
              </span>
            );
          })}

          {specialists.flatMap((specialist, specialistIndex) =>
            Array.from({ length: rowCount }, (_, row) => {
              const slotStart = dayStart + row * SLOT_MINUTES * minuteMs;
              const slotEnd = slotStart + SLOT_MINUTES * minuteMs;
              const inBreak = day.breaks.some((item) => intervalOverlaps(
                slotStart,
                slotEnd,
                new Date(item.starts_at).getTime(),
                new Date(item.ends_at).getTime(),
              ));
              const hasAppointment = visibleEvents.some((event) =>
                event.specialist.id === specialist.id && intervalOverlaps(
                  slotStart,
                  slotEnd,
                  new Date(event.starts_at).getTime(),
                  new Date(event.ends_at).getTime(),
                ));
              const startsAt = new Date(slotStart).toISOString();
              if (!inBreak && !hasAppointment) {
                return (
                  <button
                    aria-label={`Створити запис на ${timeLabel(startsAt)}, ${specialist.display_name}`}
                    className="calendar-slot calendar-slot--free"
                    key={`${String(specialist.id)}-${String(slotStart)}`}
                    onClick={() => { onSlotSelect({ specialistId: specialist.id, startsAt }); }}
                    style={{ gridColumn: specialistIndex + 2, gridRow: row + 1 }}
                    type="button"
                  >
                    {row % 4 === 0 ? <small>Вільно</small> : null}
                  </button>
                );
              }
              return (
                <span
                  aria-hidden="true"
                  className={`calendar-slot ${inBreak ? "calendar-slot--break" : ""}`}
                  key={`${String(specialist.id)}-${String(slotStart)}`}
                  style={{ gridColumn: specialistIndex + 2, gridRow: row + 1 }}
                >
                </span>
              );
            }),
          )}

          {specialists.flatMap((_, specialistIndex) => day.breaks.map((item) => {
            const startRow = Math.floor(
              (new Date(item.starts_at).getTime() - dayStart) / (SLOT_MINUTES * minuteMs),
            ) + 1;
            const span = Math.max(1, Math.ceil(minutesBetween(item.starts_at, item.ends_at) / SLOT_MINUTES));
            return (
              <div
                className="calendar-break-card"
                key={`${String(specialistIndex)}-${item.starts_at}`}
                style={{ gridColumn: specialistIndex + 2, gridRow: `${String(startRow)} / span ${String(span)}` }}
              >
                <span aria-hidden="true">☕</span>
                <span><strong>Перерва</strong><small>{timeLabel(item.starts_at)}–{timeLabel(item.ends_at)}</small></span>
              </div>
            );
          }))}

          {visibleEvents.map((event) => {
            const specialistIndex = specialists.findIndex((item) => item.id === event.specialist.id);
            const startRow = Math.floor(
              (new Date(event.starts_at).getTime() - dayStart) / (SLOT_MINUTES * minuteMs),
            ) + 1;
            const span = Math.max(1, Math.ceil(minutesBetween(event.starts_at, event.ends_at) / SLOT_MINUTES));
            return (
              <button
                aria-label={`${timeLabel(event.starts_at)} ${event.patient.display_name}, ${event.status.label}`}
                className={`calendar-event ${event.status.code === "CANCELED" ? "calendar-event--canceled" : ""}`}
                data-testid="calendar-event"
                key={event.id}
                onClick={() => { onEventSelect(event.id); }}
                style={{
                  "--event-color": event.service.color,
                  gridColumn: specialistIndex + 2,
                  gridRow: `${String(startRow)} / span ${String(span)}`,
                } as CSSProperties}
                type="button"
              >
                <span className="calendar-event__heading"><strong>{event.patient.display_name}</strong><time>{timeLabel(event.starts_at)}–{timeLabel(event.ends_at)}</time></span>
                <p>{event.service.name} · {event.room.name}</p>
                <span className="calendar-event__status" style={{ "--status-color": event.status.color } as CSSProperties}>{event.status.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function WeekCalendar({
  days,
  events,
  onEventSelect,
  specialists,
}: {
  readonly days: readonly CalendarDay[];
  readonly events: readonly CalendarEvent[];
  readonly onEventSelect: (appointmentId: string) => void;
  readonly specialists: readonly Specialist[];
}) {
  return (
    <section className="calendar-week panel" aria-label="Тижневий календар">
      <p className="calendar-scroll-hint" id="calendar-week-scroll-hint">
        <span aria-hidden="true">↔</span>
        Гортайте тиждень горизонтально; з клавіатури використовуйте стрілки.
      </p>
      <div
        aria-describedby="calendar-week-scroll-hint"
        aria-label="Прокручуваний тижневий календар"
        className="calendar-week__scroll"
        data-testid="calendar-week-scroll"
        tabIndex={0}
      >
        <div className="calendar-week__grid">
          {days.map((day) => {
            const dayEvents = eventsForDay(events, day)
              .filter((event) => specialists.some((item) => item.id === event.specialist.id))
              .sort((left, right) => left.starts_at.localeCompare(right.starts_at));
            return (
              <article className={`calendar-week-day ${day.is_working ? "" : "calendar-week-day--closed"}`} key={day.date}>
                <header>
                  <span>{shortDateFormatter.format(new Date(`${day.date}T12:00:00Z`))}</span>
                  {day.starts_at === null || day.ends_at === null ? <small>Вихідний</small> : <small>{timeLabel(day.starts_at)}–{timeLabel(day.ends_at)}</small>}
                </header>
                <div className="calendar-week-day__events">
                  {dayEvents.map((event) => (
                    <button aria-label={`${timeLabel(event.starts_at)} ${event.patient.display_name}, ${event.status.label}`} className="calendar-week-event" key={event.id} onClick={() => { onEventSelect(event.id); }} style={{ "--event-color": event.service.color } as CSSProperties} type="button">
                      <time>{timeLabel(event.starts_at)}</time>
                      <strong>{event.patient.display_name}</strong>
                      <small>{event.service.name}</small>
                      {specialists.length > 1 ? <small>{event.specialist.display_name}</small> : null}
                      <span>{event.status.label}</span>
                    </button>
                  ))}
                  {day.is_working && dayEvents.length === 0 ? <p className="calendar-week-empty"><Icon name="calendar" /><span>Записів немає<small>День вільний</small></span></p> : null}
                  {!day.is_working ? <p className="calendar-week-empty"><span aria-hidden="true">☾</span><span>Клініка зачинена<small>За графіком</small></span></p> : null}
                </div>
                {day.is_working ? <footer><span>Перерв: {day.breaks.length}</span><span>Спеціалістів: {specialists.length}</span></footer> : null}
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function CalendarPage() {
  const { state } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [view, setView] = useState<CalendarView>("day");
  const [selectedDate, setSelectedDate] = useState(() => dateKey(new Date()));
  const [selectedSpecialist, setSelectedSpecialist] = useState<number | "all">("all");
  const [data, setData] = useState<CalendarResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [slotPreset, setSlotPreset] = useState<SlotPreset | null>(null);
  const [datePickerOpen, setDatePickerOpen] = useState(false);
  const datePickerRef = useRef<HTMLDivElement>(null);
  const datePickerTriggerRef = useRef<HTMLButtonElement>(null);
  const appointmentTriggerRef = useRef<HTMLElement | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);
  const range = useMemo(() => rangeFor(view, selectedDate), [view, selectedDate]);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/calendar", {
      params: { query: range },
    }).catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Перевірте мережу й повторіть спробу.");
    } else if (result.data === undefined) {
      setError(result.error.message);
    } else {
      setData(result.data);
    }
    setIsLoading(false);
  }, [range]);

  useEffect(() => {
    void load();
  }, [load, requestVersion]);

  useEffect(() => {
    if (!datePickerOpen) return undefined;
    const handlePointerDown = (event: PointerEvent) => {
      if (
        event.target instanceof Node
        && !datePickerRef.current?.contains(event.target)
      ) {
        setDatePickerOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setDatePickerOpen(false);
      window.setTimeout(() => { datePickerTriggerRef.current?.focus(); }, 0);
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [datePickerOpen]);

  if (state.status !== "authenticated") return null;
  const isPodologist = state.session.user.role === "podologist";
  const specialists = data?.specialists ?? [];
  const visibleSpecialists = selectedSpecialist === "all"
    ? specialists
    : specialists.filter((item) => item.id === selectedSpecialist);
  const visibleEvents = (data?.events ?? []).filter((event) =>
    selectedSpecialist === "all" || event.specialist.id === selectedSpecialist);
  const move = (direction: -1 | 1) => {
    setSelectedDate((current) => addDays(current, direction * (view === "week" ? 7 : 1)));
  };
  const dateHeading = view === "week"
    ? `${shortDateFormatter.format(zonedMidnight(startOfWeek(selectedDate)))} — ${shortDateFormatter.format(zonedMidnight(addDays(startOfWeek(selectedDate), 6)))}`
    : dateFormatter.format(zonedMidnight(selectedDate));
  const isCreatingAppointment = searchParams.get("compose") === "appointment";
  const presetPatientId = searchParams.get("patient") ?? undefined;
  const openAppointment = (preset: SlotPreset | null = null) => {
    setSlotPreset(preset);
    setSuccess(null);
    const next = new URLSearchParams(searchParams);
    next.set("compose", "appointment");
    next.delete("appointment");
    if (preset !== null) next.delete("patient");
    setSearchParams(next);
  };
  const closeAppointment = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("compose");
    next.delete("patient");
    setSearchParams(next, { replace: true });
    setSlotPreset(null);
  };
  const openAppointmentDetail = (appointmentId: string) => {
    appointmentTriggerRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const next = new URLSearchParams(searchParams);
    next.delete("compose");
    next.delete("patient");
    next.set("appointment", appointmentId);
    setSearchParams(next);
  };
  const closeAppointmentDetail = () => {
    const trigger = appointmentTriggerRef.current;
    const next = new URLSearchParams(searchParams);
    next.delete("appointment");
    setSearchParams(next, { replace: true });
    window.setTimeout(() => { trigger?.focus(); }, 0);
  };
  const selectedAppointmentId = searchParams.get("appointment");

  return (
    <>
      <header className="page-heading calendar-heading">
        <div>
          <p className="eyebrow">Календар · TP-401/402/403/404</p>
          <h1>Розклад клініки</h1>
          <p>{isPodologist ? "Ваші записи та вільні вікна." : "Спільний календар усіх активних спеціалістів."}</p>
        </div>
        <div className="calendar-heading__actions"><button className="button button--primary" onClick={() => { openAppointment(); }} type="button"><Icon name="plus" />Новий запис</button><span className="patient-scope-pill"><Icon name="lock" /> Доступ: {roleLabels[state.session.user.role]}</span></div>
      </header>

      {success ? <div className="success-banner" role="status"><Icon name="calendar" /><span>{success}</span></div> : null}

      <section className="calendar-toolbar panel" aria-label="Керування календарем">
        <div className="segmented-control" aria-label="Вигляд календаря">
          <button aria-pressed={view === "day"} onClick={() => { setView("day"); }} type="button">День</button>
          <button aria-pressed={view === "week"} onClick={() => { setView("week"); }} type="button">Тиждень</button>
        </div>
        <div className="calendar-date-navigation">
          <button className="icon-button" onClick={() => { move(-1); }} type="button" aria-label={view === "day" ? "Попередній день" : "Попередній тиждень"}><Icon name="arrow-left" /></button>
          <div className="calendar-date-navigation__picker" ref={datePickerRef}>
            <button
              aria-expanded={datePickerOpen}
              aria-haspopup="dialog"
              aria-label={`Обрати дату: ${dateHeading}`}
              className="calendar-date-navigation__today"
              onClick={() => { setDatePickerOpen((current) => !current); }}
              ref={datePickerTriggerRef}
              type="button"
            >
              <Icon name="calendar" />
              <span>{dateHeading}</span>
              <Icon className="calendar-date-navigation__caret" name="chevron" />
            </button>
            {datePickerOpen ? (
              <CalendarDatePicker
                onClose={() => {
                  setDatePickerOpen(false);
                  window.setTimeout(() => { datePickerTriggerRef.current?.focus(); }, 0);
                }}
                onSelect={(date) => {
                  setSelectedDate(date);
                  setDatePickerOpen(false);
                  window.setTimeout(() => { datePickerTriggerRef.current?.focus(); }, 0);
                }}
                onViewChange={setView}
                selectedDate={selectedDate}
                today={dateKey(new Date())}
                view={view}
              />
            ) : null}
          </div>
          <button className="icon-button" onClick={() => { move(1); }} type="button" aria-label={view === "day" ? "Наступний день" : "Наступний тиждень"}><Icon name="chevron" /></button>
        </div>
        {isPodologist ? (
          <span className="calendar-own-scope"><Icon name="lock" /> Лише моя колонка</span>
        ) : (
          <label className="calendar-specialist-filter">
            <span>Спеціаліст</span>
            <select aria-label="Спеціаліст" onChange={(event) => { setSelectedSpecialist(event.target.value === "all" ? "all" : Number(event.target.value)); }} value={selectedSpecialist}>
              <option value="all">Усі спеціалісти</option>
              {specialists.map((specialist) => <option key={specialist.id} value={specialist.id}>{specialist.display_name}</option>)}
            </select>
          </label>
        )}
      </section>

      {isLoading ? <CalendarLoading /> : null}
      {!isLoading && error !== null ? (
        <section className="calendar-error panel" role="alert">
          <span className="calendar-closed__icon calendar-closed__icon--error"><Icon name="warning" /></span>
          <div><h2>Не вдалося завантажити календар</h2><p>{error}</p></div>
          <button className="button button--secondary" onClick={() => { setRequestVersion((current) => current + 1); }} type="button">Повторити</button>
        </section>
      ) : null}
      {!isLoading && error === null && data !== null && view === "day" ? (
        <DayCalendar day={data.days[0]} events={visibleEvents} onEventSelect={openAppointmentDetail} onSlotSelect={(preset) => { openAppointment(preset); }} specialists={visibleSpecialists} />
      ) : null}
      {!isLoading && error === null && data !== null && view === "week" ? (
        <WeekCalendar days={data.days} events={visibleEvents} onEventSelect={openAppointmentDetail} specialists={visibleSpecialists} />
      ) : null}
      {isCreatingAppointment && data !== null ? (
        <AppointmentCreateDialog
          initialDate={selectedDate}
          onClose={closeAppointment}
          onSaved={(appointment) => {
            closeAppointment();
            setSuccess(`Запис ${appointment.public_number} для ${appointment.patient.display_name} створено.`);
            setRequestVersion((current) => current + 1);
          }}
          presetSlot={slotPreset}
          specialists={specialists}
          {...(presetPatientId === undefined ? {} : { presetPatientId })}
        />
      ) : null}
      {selectedAppointmentId !== null && data !== null ? (
        <AppointmentDetailDialog
          appointmentId={selectedAppointmentId}
          onChanged={(appointment, message) => {
            setSuccess(message);
            setRequestVersion((current) => current + 1);
            const next = new URLSearchParams(searchParams);
            next.set("appointment", appointment.id);
            setSearchParams(next, { replace: true });
          }}
          onClose={closeAppointmentDetail}
          onVisitOpened={(visitId) => {
            const next = new URLSearchParams(searchParams);
            next.delete("appointment");
            setSearchParams(next, { replace: true });
            void navigate(`/visits/${visitId}`);
          }}
          specialists={specialists}
        />
      ) : null}
    </>
  );
}
