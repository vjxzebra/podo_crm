import { useEffect, useMemo, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";

type ClinicWorkday = components["schemas"]["ClinicWorkday"];

interface BreakDraft {
  readonly start_time: string;
  readonly end_time: string;
}

interface WorkdayDraft {
  readonly weekday: number;
  readonly is_working: boolean;
  readonly start_time: string | null;
  readonly end_time: string | null;
  readonly breaks: readonly BreakDraft[];
  readonly version: number;
}

const weekdayLabels = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"] as const;

function toDraft(workdays: readonly ClinicWorkday[]): readonly WorkdayDraft[] {
  return workdays.map((item) => ({
    weekday: item.weekday,
    is_working: item.is_working ?? false,
    start_time: item.start_time,
    end_time: item.end_time,
    breaks: item.breaks.map((scheduleBreak) => ({
      start_time: scheduleBreak.start_time,
      end_time: scheduleBreak.end_time,
    })),
    version: item.version ?? 1,
  }));
}

function firstFieldError(fields: Readonly<Record<string, readonly string[]>>): string | null {
  return Object.values(fields).find((messages) => messages.length > 0)?.[0] ?? null;
}

export function ScheduleSettings() {
  const [savedDays, setSavedDays] = useState<readonly WorkdayDraft[] | null>(null);
  const [days, setDays] = useState<readonly WorkdayDraft[] | null>(null);
  const [timezone, setTimezone] = useState("Europe/Kyiv");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    const result = await apiClient.GET("/api/v1/clinic-workdays").catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
    } else {
      const next = toDraft(result.data.workdays);
      setTimezone(result.data.timezone);
      setSavedDays(next);
      setDays(next);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const isDirty = useMemo(() => days !== null && savedDays !== null && JSON.stringify(days) !== JSON.stringify(savedDays), [days, savedDays]);
  const updateDay = (weekday: number, update: (day: WorkdayDraft) => WorkdayDraft) => {
    setDays((current) => current?.map((item) => item.weekday === weekday ? update(item) : item) ?? current);
    setSuccess(null);
  };
  const updateBreak = (weekday: number, index: number, field: keyof BreakDraft, value: string) => {
    updateDay(weekday, (day) => ({ ...day, breaks: day.breaks.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item) }));
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    if (days === null) return;
    setIsSaving(true);
    setError(null);
    setSuccess(null);
    const result = await apiClient.PUT("/api/v1/clinic-workdays", {
      body: { workdays: days.map((item) => ({ ...item, breaks: [...item.breaks] })) },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(firstFieldError(result.error.fields) ?? result.error.message);
    } else {
      const next = toDraft(result.data.workdays);
      setSavedDays(next);
      setDays(next);
      setTimezone(result.data.timezone);
      setSuccess("Єдиний графік клініки збережено.");
    }
    setIsSaving(false);
  };

  return (
    <section className="panel schedule-panel">
      <header><div><p className="eyebrow">Одна локація · ADR-002</p><h2>Робочий час клініки</h2><p>Спільний повторюваний тиждень для всіх спеціалістів і кімнат. Перерви виключають час із майбутньої availability.</p></div><span className="timezone-badge"><Icon name="calendar" />{timezone}</span></header>
      {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span>{error.includes("іншій сесії") ? <button className="text-action" onClick={() => void load()} type="button">Оновити</button> : null}</div>}
      {success === null ? null : <div className="form-message form-message--success" role="status"><Icon name="settings" /><span>{success}</span></div>}
      {days === null && error === null ? <div className="settings-state"><span className="spinner" /><p>Завантажуємо тижневий графік…</p></div> : null}
      {days === null ? null : <form onSubmit={(event) => void submit(event)}>
        <div className="schedule-days">{days.map((day) => {
          const dayLabel = weekdayLabels[day.weekday] ?? `День ${String(day.weekday + 1)}`;
          return <article className={day.is_working ? "schedule-day" : "schedule-day schedule-day--closed"} key={day.weekday}>
            <header><div><strong>{dayLabel}</strong><small>{day.is_working ? `${day.start_time ?? "—"}–${day.end_time ?? "—"}` : "Вихідний"}</small></div><label className="schedule-switch"><input aria-label={`${dayLabel} робочий`} checked={day.is_working} onChange={(event) => { updateDay(day.weekday, (current) => event.target.checked ? { ...current, is_working: true, start_time: current.start_time ?? "09:00", end_time: current.end_time ?? "18:00" } : { ...current, is_working: false, start_time: null, end_time: null, breaks: [] }); }} type="checkbox" /><span>{day.is_working ? "Робочий" : "Вихідний"}</span></label></header>
            {day.is_working ? <div className="schedule-day__body">
              <div className="schedule-hours"><label className="form-field"><span>Початок</span><input aria-label={`${dayLabel} початок`} onChange={(event) => { updateDay(day.weekday, (current) => ({ ...current, start_time: event.target.value })); }} required type="time" value={day.start_time ?? ""} /></label><span>—</span><label className="form-field"><span>Завершення</span><input aria-label={`${dayLabel} завершення`} onChange={(event) => { updateDay(day.weekday, (current) => ({ ...current, end_time: event.target.value })); }} required type="time" value={day.end_time ?? ""} /></label></div>
              <div className="schedule-breaks"><div className="schedule-breaks__title"><span><strong>Перерви</strong><small>{day.breaks.length === 0 ? "Без перерв" : `${String(day.breaks.length)} у графіку`}</small></span><button className="text-action" onClick={() => { updateDay(day.weekday, (current) => ({ ...current, breaks: [...current.breaks, { start_time: "13:00", end_time: "14:00" }] })); }} type="button"><Icon name="plus" />Додати</button></div>{day.breaks.map((scheduleBreak, index) => <div className="schedule-break" key={`${String(day.weekday)}-${String(index)}`}><input aria-label={`${dayLabel} перерва ${String(index + 1)} початок`} onChange={(event) => { updateBreak(day.weekday, index, "start_time", event.target.value); }} required type="time" value={scheduleBreak.start_time} /><span>—</span><input aria-label={`${dayLabel} перерва ${String(index + 1)} завершення`} onChange={(event) => { updateBreak(day.weekday, index, "end_time", event.target.value); }} required type="time" value={scheduleBreak.end_time} /><button className="icon-button" onClick={() => { updateDay(day.weekday, (current) => ({ ...current, breaks: current.breaks.filter((_, itemIndex) => itemIndex !== index) })); }} type="button" aria-label={`Видалити перерву ${String(index + 1)} у ${dayLabel}`}><Icon name="close" /></button></div>)}</div>
            </div> : <p className="schedule-closed-copy">Нові записи на цей день не пропонуватимуться.</p>}
          </article>;
        })}</div>
        <footer className="schedule-actions"><span>{isDirty ? <><Icon name="warning" />Є незбережені зміни</> : "Графік синхронізовано"}</span><button className="button button--secondary" disabled={!isDirty || isSaving} onClick={() => { setDays(savedDays); setError(null); }} type="button">Скасувати зміни</button><button className="button button--primary" disabled={!isDirty || isSaving} type="submit">{isSaving ? "Зберігаємо…" : "Зберегти графік"}</button></footer>
      </form>}
      <footer className="rooms-history-note"><Icon name="lock" /><span><strong>Лише clinic-wide schedule</strong><small>Індивідуальні графіки, свята, відпустки, винятки, timezone picker і крок календаря не входять до MVP.</small></span></footer>
    </section>
  );
}
