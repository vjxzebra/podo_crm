import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { Icon } from "../app/Icon";

type CalendarView = "day" | "week";

const CLINIC_TIMEZONE = "Europe/Kyiv";
const weekdayLabels = [
  ["Пн", "Понеділок"],
  ["Вт", "Вівторок"],
  ["Ср", "Середа"],
  ["Чт", "Четвер"],
  ["Пт", "П’ятниця"],
  ["Сб", "Субота"],
  ["Нд", "Неділя"],
] as const;

const monthFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: CLINIC_TIMEZONE,
  month: "long",
  year: "numeric",
});

const fullDateFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: CLINIC_TIMEZONE,
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

const shortDateFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: CLINIC_TIMEZONE,
  day: "numeric",
  month: "short",
});

function parseDateKey(value: string): readonly [number, number, number] {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (match?.[1] === undefined || match[2] === undefined || match[3] === undefined) {
    throw new Error("Invalid calendar date key.");
  }
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function dateForFormatting(value: string): Date {
  const [year, month, day] = parseDateKey(value);
  return new Date(Date.UTC(year, month - 1, day, 12));
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

function shiftMonth(value: string, amount: number): string {
  const [year, month] = value.split("-").map(Number);
  if (year === undefined || month === undefined) {
    throw new Error("Invalid calendar month key.");
  }
  return new Date(Date.UTC(year, month - 1 + amount, 1)).toISOString().slice(0, 7);
}

function monthDays(month: string): readonly string[] {
  const firstDay = `${month}-01`;
  const gridStart = startOfWeek(firstDay);
  return Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
}

function dateLabel(value: string): string {
  return fullDateFormatter.format(dateForFormatting(value));
}

export function CalendarDatePicker({
  onClose,
  onSelect,
  onViewChange,
  selectedDate,
  today,
  view,
}: {
  readonly onClose: () => void;
  readonly onSelect: (date: string) => void;
  readonly onViewChange: (view: CalendarView) => void;
  readonly selectedDate: string;
  readonly today: string;
  readonly view: CalendarView;
}) {
  const [visibleMonth, setVisibleMonth] = useState(selectedDate.slice(0, 7));
  const [focusedDate, setFocusedDate] = useState(selectedDate);
  const rootRef = useRef<HTMLDivElement>(null);
  const initialFocusRef = useRef<HTMLButtonElement>(null);
  const days = useMemo(() => monthDays(visibleMonth), [visibleMonth]);
  const selectedWeekStart = startOfWeek(selectedDate);
  const selectedWeekEnd = addDays(selectedWeekStart, 6);

  useEffect(() => {
    initialFocusRef.current?.focus();
  }, []);

  const focusDay = (date: string) => {
    setFocusedDate(date);
    if (date.slice(0, 7) !== visibleMonth) {
      setVisibleMonth(date.slice(0, 7));
    }
    window.setTimeout(() => {
      rootRef.current
        ?.querySelector<HTMLButtonElement>(`[data-calendar-date="${date}"]`)
        ?.focus();
    }, 0);
  };

  const handleDayKeyDown = (event: KeyboardEvent<HTMLButtonElement>, date: string) => {
    let nextDate: string | null = null;
    if (event.key === "ArrowLeft") nextDate = addDays(date, -1);
    if (event.key === "ArrowRight") nextDate = addDays(date, 1);
    if (event.key === "ArrowUp") nextDate = addDays(date, -7);
    if (event.key === "ArrowDown") nextDate = addDays(date, 7);
    if (event.key === "Home") nextDate = startOfWeek(date);
    if (event.key === "End") nextDate = addDays(startOfWeek(date), 6);
    if (nextDate === null) return;
    event.preventDefault();
    focusDay(nextDate);
  };
  const changeVisibleMonth = (amount: number) => {
    const nextMonth = shiftMonth(visibleMonth, amount);
    setVisibleMonth(nextMonth);
    setFocusedDate(`${nextMonth}-01`);
  };

  const selectionSummary = view === "week"
    ? `${shortDateFormatter.format(dateForFormatting(selectedWeekStart))} — ${shortDateFormatter.format(dateForFormatting(selectedWeekEnd))}`
    : shortDateFormatter.format(dateForFormatting(selectedDate));

  return (
    <div
      aria-label="Вибір дати календаря"
      className="calendar-date-picker"
      ref={rootRef}
      role="dialog"
    >
      <div className="calendar-date-picker__heading">
        <div>
          <span>Перейти до</span>
          <strong>Дати або тижня</strong>
        </div>
        <button
          aria-label="Закрити вибір дати"
          className="icon-button"
          onClick={onClose}
          type="button"
        >
          <Icon name="close" />
        </button>
      </div>

      <div aria-label="Вигляд у виборі дати" className="calendar-date-picker__mode segmented-control">
        <button
          aria-pressed={view === "day"}
          onClick={() => { onViewChange("day"); }}
          type="button"
        >
          День
        </button>
        <button
          aria-pressed={view === "week"}
          onClick={() => { onViewChange("week"); }}
          type="button"
        >
          Тиждень
        </button>
      </div>

      <div className="calendar-date-picker__month">
        <button
          aria-label="Попередній місяць"
          className="icon-button"
          onClick={() => { changeVisibleMonth(-1); }}
          type="button"
        >
          <Icon name="arrow-left" />
        </button>
        <strong aria-live="polite">
          {monthFormatter.format(dateForFormatting(`${visibleMonth}-01`))}
        </strong>
        <button
          aria-label="Наступний місяць"
          className="icon-button"
          onClick={() => { changeVisibleMonth(1); }}
          type="button"
        >
          <Icon name="chevron" />
        </button>
      </div>

      <div aria-hidden="true" className="calendar-date-picker__weekdays">
        {weekdayLabels.map(([shortLabel, longLabel]) => (
          <abbr key={shortLabel} title={longLabel}>{shortLabel}</abbr>
        ))}
      </div>

      <div
        aria-label={`Дні місяця, ${monthFormatter.format(dateForFormatting(`${visibleMonth}-01`))}`}
        className="calendar-date-picker__grid"
        role="group"
      >
        {days.map((date) => {
          const outsideMonth = date.slice(0, 7) !== visibleMonth;
          const isSelected = date === selectedDate;
          const isSelectedWeek = view === "week"
            && date >= selectedWeekStart
            && date <= selectedWeekEnd;
          const classNames = [
            "calendar-date-picker__day",
            outsideMonth ? "calendar-date-picker__day--outside" : "",
            date === today ? "calendar-date-picker__day--today" : "",
            isSelected ? "calendar-date-picker__day--selected" : "",
            isSelectedWeek ? "calendar-date-picker__day--week" : "",
            isSelectedWeek && date === selectedWeekStart
              ? "calendar-date-picker__day--week-start"
              : "",
            isSelectedWeek && date === selectedWeekEnd
              ? "calendar-date-picker__day--week-end"
              : "",
          ].filter(Boolean).join(" ");
          return (
            <button
              aria-current={date === today ? "date" : undefined}
              aria-label={`${dateLabel(date)}${isSelectedWeek ? ", вибраний тиждень" : ""}`}
              aria-pressed={isSelected}
              className={classNames}
              data-calendar-date={date}
              key={date}
              onClick={() => { onSelect(date); }}
              onFocus={() => { setFocusedDate(date); }}
              onKeyDown={(event) => { handleDayKeyDown(event, date); }}
              ref={isSelected ? initialFocusRef : undefined}
              tabIndex={date === focusedDate ? 0 : -1}
              type="button"
            >
              <span>{String(Number(date.slice(-2)))}</span>
            </button>
          );
        })}
      </div>

      <div className="calendar-date-picker__footer">
        <span><Icon name="calendar" />{view === "week" ? "Вибраний тиждень" : "Вибрана дата"}: {selectionSummary}</span>
        <button onClick={() => { onSelect(today); }} type="button">Сьогодні</button>
      </div>
    </div>
  );
}
