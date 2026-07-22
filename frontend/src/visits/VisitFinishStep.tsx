import { useEffect, useMemo, useRef, useState } from "react";

import { apiClient } from "../api/client";
import type { components, operations } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders, useAuth } from "../auth/AuthContext";

type Visit = components["schemas"]["VisitResponse"];
type FinishResult = components["schemas"]["VisitFinishResponse"];
type Availability = components["schemas"]["AvailabilityResponse"];
type Specialist = components["schemas"]["SpecialistSummary"];
type FinishRequest = NonNullable<operations["visit_finish"]["requestBody"]>["content"]["application/json"];

type VisitFinishStepProps = Readonly<{
  visit: Visit;
  onBack: () => void;
  onCompleted: (result: FinishResult) => void;
}>;

const moneyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
  minimumFractionDigits: 2,
});

const timeFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function money(minor: number): string {
  return moneyFormatter.format(minor / 100);
}

function nextUtcDay(value: string): string {
  const date = new Date(`${value}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString();
}

function todayInputValue(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Kyiv",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

export function VisitFinishStep({ visit, onBack, onCompleted }: VisitFinishStepProps) {
  const { state } = useAuth();
  const primaryService = visit.service_lines.find((line) => line.is_primary)
    ?? visit.service_lines[0];
  const [recommendations, setRecommendations] = useState("");
  const [handoffRequested, setHandoffRequested] = useState(true);
  const [scheduleFollowUp, setScheduleFollowUp] = useState(false);
  const [followUpDate, setFollowUpDate] = useState("");
  const [serviceId, setServiceId] = useState(primaryService?.service_id ?? "");
  const [specialistId, setSpecialistId] = useState(String(visit.specialist.id));
  const [specialists, setSpecialists] = useState<readonly Specialist[]>([visit.specialist]);
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [availabilityState, setAvailabilityState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [startsAt, setStartsAt] = useState("");
  const [roomId, setRoomId] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availabilityVersion, setAvailabilityVersion] = useState(0);
  const finishKey = useRef(crypto.randomUUID());

  const beforeCount = visit.photos.filter((photo) => photo.kind === "BEFORE").length;
  const afterCount = visit.photos.filter((photo) => photo.kind === "AFTER").length;
  const totalMinor = visit.services_total_minor;
  const materialQuantity = useMemo(() => visit.material_lines.reduce(
    (total, line) => total + Number(line.quantity),
    0,
  ), [visit.material_lines]);

  const markChanged = () => {
    finishKey.current = crypto.randomUUID();
    setConfirmed(false);
    setError(null);
  };

  useEffect(() => {
    if (!scheduleFollowUp || followUpDate === "") {
      setSpecialists([visit.specialist]);
      return;
    }
    const controller = new AbortController();
    void apiClient.GET("/api/v1/calendar", {
      params: {
        query: {
          from: `${followUpDate}T00:00:00.000Z`,
          to: nextUtcDay(followUpDate),
        },
      },
      signal: controller.signal,
    }).then((result) => {
      if (result.data === undefined) return;
      setSpecialists(result.data.specialists);
      if (!result.data.specialists.some((item) => String(item.id) === specialistId)) {
        const fallback = result.data.specialists[0];
        setSpecialistId(fallback === undefined ? "" : String(fallback.id));
      }
    }).catch(() => undefined);
    return () => { controller.abort(); };
  }, [followUpDate, scheduleFollowUp, specialistId, visit.specialist]);

  useEffect(() => {
    if (!scheduleFollowUp || followUpDate === "" || serviceId === "" || specialistId === "") {
      setAvailability(null);
      setAvailabilityState("idle");
      setStartsAt("");
      setRoomId("");
      return;
    }
    const controller = new AbortController();
    setAvailabilityState("loading");
    setAvailabilityError(null);
    setStartsAt("");
    setRoomId("");
    void apiClient.GET("/api/v1/appointments/availability", {
      params: {
        query: {
          date: followUpDate,
          service_id: serviceId,
          specialist_id: Number(specialistId),
        },
      },
      signal: controller.signal,
    }).then((result) => {
      if (result.data === undefined) {
        setAvailability(null);
        setAvailabilityState("error");
        setAvailabilityError(result.error.message);
        return;
      }
      setAvailability(result.data);
      setAvailabilityState("ready");
    }).catch((reason: unknown) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setAvailability(null);
      setAvailabilityState("error");
      setAvailabilityError("Не вдалося перевірити вільні години. Повторіть спробу.");
    });
    return () => { controller.abort(); };
  }, [availabilityVersion, followUpDate, scheduleFollowUp, serviceId, specialistId]);

  const followUpValid = !scheduleFollowUp || (
    followUpDate !== ""
    && serviceId !== ""
    && specialistId !== ""
    && startsAt !== ""
    && roomId !== ""
  );

  const submit = async () => {
    if (!confirmed || !followUpValid || isSubmitting) return;
    const body: FinishRequest = {
      version: visit.version,
      recommendations,
      payment_handoff_requested: handoffRequested,
      follow_up: scheduleFollowUp ? {
        starts_at: startsAt,
        service_id: serviceId,
        specialist_id: Number(specialistId),
        room_id: roomId,
      } : null,
    };
    setIsSubmitting(true);
    setError(null);
    const result = await apiClient.POST("/api/v1/visits/{visit_id}/finish", {
      params: {
        path: { visit_id: visit.id },
        header: { "Idempotency-Key": finishKey.current },
      },
      body,
      headers: csrfHeaders(),
    }).catch(() => null);
    setIsSubmitting(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Дані не втрачено — повторіть завершення.");
      return;
    }
    if (result.data === undefined) {
      if (result.error.code === "appointment_slot_conflict") {
        setAvailabilityVersion((current) => current + 1);
        setError("Обране вікно вже зайняли. Виберіть інший доступний час і підтвердьте ще раз.");
        setConfirmed(false);
        finishKey.current = crypto.randomUUID();
        return;
      }
      if (result.error.code === "idempotency_payload_mismatch") {
        finishKey.current = crypto.randomUUID();
      }
      setError(result.error.code === "insufficient_stock"
        ? "Залишок матеріалу змінився. Поверніться до кроку 2, оновіть партію або кількість і повторіть."
        : result.error.message);
      return;
    }
    onCompleted(result.data);
  };

  return (
    <section className="visit-examination visit-finish-panel panel" aria-labelledby="visit-finish-title">
      <header>
        <div>
          <p className="eyebrow">Крок 4 із 4</p>
          <h2 id="visit-finish-title">Перевірка та завершення</h2>
          <p>Один submit атомарно завершує прийом, списує матеріали й формує повну суму до оплати.</p>
        </div>
        <span className={`visit-save-state${isSubmitting ? " visit-save-state--saving" : ""}`} role="status">
          <span aria-hidden="true" />{isSubmitting ? "Завершуємо…" : "Готово до перевірки"}
        </span>
      </header>

      {error ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}

      <div className="visit-finish-grid">
        <section className="visit-finish-summary" aria-labelledby="visit-finish-services">
          <header><div><p className="eyebrow">Підсумок</p><h3 id="visit-finish-services">Послуги та сума</h3></div><strong>{money(totalMinor)}</strong></header>
          <ul>
            {visit.service_lines.map((line) => (
              <li key={line.id}><div><strong>{line.service_name}</strong><small>{line.service_code} · {money(line.price_minor)} за одиницю</small></div><span>{line.quantity} ×</span><b>{money(line.line_total_minor)}</b></li>
            ))}
          </ul>
        </section>

        <section className="visit-finish-facts" aria-label="Матеріали та фото">
          <article><span>Матеріали</span><strong>{visit.material_lines.length} партій</strong><small>Фактична кількість: {materialQuantity.toLocaleString("uk-UA")}</small></article>
          <article><span>Фото ДО</span><strong>{beforeCount}</strong><small>{beforeCount > 0 ? "Додано до прийому" : "Не додано"}</small></article>
          <article><span>Фото ПІСЛЯ</span><strong>{afterCount}</strong><small>{afterCount > 0 ? "Додано до прийому" : "Не додано"}</small></article>
        </section>

        <label className="form-field visit-finish-wide">
          <span>Рекомендації пацієнту · необов’язково</span>
          <textarea disabled={isSubmitting} maxLength={10000} onChange={(event) => { setRecommendations(event.target.value); markChanged(); }} placeholder="Домашній догляд, частота процедур, застереження" rows={5} value={recommendations} />
          <small>Рекомендації збережуться з автором і датою; ресепшн не бачить їх змісту.</small>
        </label>

        <label className="settings-check visit-finish-wide">
          <input checked={handoffRequested} disabled={isSubmitting} onChange={(event) => { setHandoffRequested(event.target.checked); markChanged(); }} type="checkbox" />
          <span><strong>Передати ресепшну на оплату</strong><small>Фінансове зобов’язання на {money(totalMinor)} створюється без проведення самої оплати.</small></span>
        </label>

        <fieldset className="visit-follow-up visit-finish-wide" disabled={isSubmitting}>
          <legend>Наступний запис</legend>
          <label className="settings-check">
            <input checked={scheduleFollowUp} onChange={(event) => { setScheduleFollowUp(event.target.checked); setStartsAt(""); setRoomId(""); markChanged(); }} type="checkbox" />
            <span><strong>Записати на наступний прийом</strong><small>У finish потрапить лише вибране вільне вікно.</small></span>
          </label>
          {scheduleFollowUp ? (
            <div className="visit-follow-up__fields">
              <label className="form-field"><span>Дата</span><input min={todayInputValue()} onChange={(event) => { setFollowUpDate(event.target.value); markChanged(); }} type="date" value={followUpDate} /></label>
              <label className="form-field"><span>Послуга</span><select onChange={(event) => { setServiceId(event.target.value); markChanged(); }} value={serviceId}><option value="">Оберіть послугу</option>{visit.service_lines.map((line) => <option key={line.service_id} value={line.service_id}>{line.service_name}</option>)}</select></label>
              <label className="form-field"><span>Спеціаліст</span><select onChange={(event) => { setSpecialistId(event.target.value); markChanged(); }} value={specialistId}><option value="">Оберіть спеціаліста</option>{specialists.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select>{state.status === "authenticated" && state.session.user.role === "podologist" ? <small>Подолог створює наступний запис лише до себе.</small> : null}</label>
              <label className="form-field"><span>Вільний час</span><select disabled={availabilityState !== "ready"} onChange={(event) => { const value = event.target.value; const slot = availability?.slots.find((item) => item.starts_at === value); setStartsAt(value); setRoomId(slot?.rooms[0]?.id ?? ""); markChanged(); }} value={startsAt}><option value="">{availabilityState === "loading" ? "Перевіряємо…" : "Оберіть час"}</option>{availability?.slots.map((slot) => <option key={slot.starts_at} value={slot.starts_at}>{timeFormatter.format(new Date(slot.starts_at))}–{timeFormatter.format(new Date(slot.ends_at))}</option>)}</select></label>
              <div className={`visit-follow-up__availability${availabilityState === "error" ? " visit-follow-up__availability--error" : ""}`} role="status">
                <Icon name={availabilityState === "error" ? "warning" : "calendar"} />
                <span>{availabilityError ?? (availabilityState === "ready" ? availability?.slots.length === 0 ? "Вільних вікон немає." : `Доступних вікон: ${String(availability?.slots.length ?? 0)}` : "Оберіть дату, послугу та спеціаліста.")}</span>
              </div>
            </div>
          ) : null}
        </fieldset>

        <label className="visit-finish-confirm visit-finish-wide">
          <input checked={confirmed} disabled={isSubmitting || !followUpValid} onChange={(event) => { setConfirmed(event.target.checked); setError(null); }} type="checkbox" />
          <span><strong>Підтверджую підсумок прийому</strong><small>Після завершення чернетку, фото й матеріали не можна буде редагувати звичайним способом.</small></span>
        </label>
      </div>

      <footer className="visit-workspace__footer">
        <div><strong>До оплати: {money(totalMinor)}</strong><small>Усі складські, фінансові та scheduling-зміни або commit-яться разом, або повністю відкотяться.</small></div>
        <div>
          <button className="button button--secondary" disabled={isSubmitting} onClick={onBack} type="button">Назад до фото</button>
          <button className="button button--primary" disabled={!confirmed || !followUpValid || isSubmitting} onClick={() => { void submit(); }} type="button">{isSubmitting ? "Завершуємо…" : handoffRequested ? "Завершити й передати на оплату" : "Завершити прийом"}</button>
        </div>
      </footer>
    </section>
  );
}

export type { FinishResult };
