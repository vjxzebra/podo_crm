import { useEffect, useMemo, useRef, useState } from "react";

import { apiClient } from "../api/client";
import type { components, operations } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders, useAuth } from "../auth/AuthContext";
import { ServiceMultiSelect } from "../calendar/ServiceMultiSelect";
import {
  listDiscounts,
  type Discount,
  type VisitPricingProjection,
} from "../discounts/discountApi";

type Visit = components["schemas"]["VisitResponse"];
type GeneratedFinishResult = components["schemas"]["VisitFinishResponse"];
type FinishResult = Omit<GeneratedFinishResult, "pricing"> & { readonly pricing?: VisitPricingProjection };
type Availability = components["schemas"]["AvailabilityResponse"];
type Service = components["schemas"]["Service"];
type Specialist = components["schemas"]["SpecialistSummary"];
type FinishRequest = NonNullable<operations["visit_finish"]["requestBody"]>["content"]["application/json"];
type MultiServiceFollowUp = Omit<NonNullable<FinishRequest["follow_up"]>, "service_id"> & {
  service_ids: string[];
};
type MultiServiceFinishRequest = Omit<FinishRequest, "follow_up"> & {
  follow_up: MultiServiceFollowUp | null;
  discount_id?: string;
};

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

function previewDiscountMinor(grossMinor: number, percent: number): number {
  const hundreds = Math.floor(grossMinor / 100);
  const remainder = grossMinor % 100;
  return hundreds * percent + Math.floor(remainder * percent / 100);
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
  const [recommendations, setRecommendations] = useState("");
  const [handoffRequested, setHandoffRequested] = useState(true);
  const [scheduleFollowUp, setScheduleFollowUp] = useState(false);
  const [followUpDate, setFollowUpDate] = useState("");
  const [services, setServices] = useState<readonly Service[]>([]);
  const [isLoadingServices, setIsLoadingServices] = useState(true);
  const [serviceIds, setServiceIds] = useState<readonly string[]>(
    visit.service_lines.map((line) => line.service_id),
  );
  const [specialistId, setSpecialistId] = useState(String(visit.specialist.id));
  const [specialists, setSpecialists] = useState<readonly Specialist[]>([visit.specialist]);
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [availabilityState, setAvailabilityState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [startsAt, setStartsAt] = useState("");
  const [roomId, setRoomId] = useState("");
  const [discounts, setDiscounts] = useState<readonly Discount[]>([]);
  const [selectedDiscountId, setSelectedDiscountId] = useState("");
  const [isLoadingDiscounts, setIsLoadingDiscounts] = useState(true);
  const [discountError, setDiscountError] = useState<string | null>(null);
  const [discountLoadVersion, setDiscountLoadVersion] = useState(0);
  const [confirmed, setConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availabilityVersion, setAvailabilityVersion] = useState(0);
  const finishKey = useRef(crypto.randomUUID());

  const beforeCount = visit.photos.filter((photo) => photo.kind === "BEFORE").length;
  const afterCount = visit.photos.filter((photo) => photo.kind === "AFTER").length;
  const totalMinor = visit.services_total_minor;
  const selectedDiscount = discounts.find((discount) => discount.id === selectedDiscountId);
  const loyaltyDiscount = visit.loyalty.eligible ? visit.loyalty.discount : null;
  // Manual choice replaces the loyalty discount; they never stack. The server
  // re-derives the same precedence under lock during finish.
  const effectiveDiscount = selectedDiscount ?? loyaltyDiscount;
  const loyaltyOverride = selectedDiscount !== undefined && loyaltyDiscount !== null
    ? {
      manual: selectedDiscount,
      loyalty: loyaltyDiscount,
      downgrades: selectedDiscount.percent < loyaltyDiscount.percent,
    }
    : null;
  const discountMinor = totalMinor === 0 || effectiveDiscount === null
    ? 0
    : previewDiscountMinor(totalMinor, effectiveDiscount.percent);
  const netMinor = totalMinor - discountMinor;
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
    const controller = new AbortController();
    setIsLoadingDiscounts(true);
    setDiscountError(null);
    void listDiscounts("active", controller.signal).then((result) => {
      if (!result.ok) {
        setDiscounts([]);
        setSelectedDiscountId("");
        setDiscountError(result.error.message);
        return;
      }
      setDiscounts(result.data.discounts.filter((discount) => discount.is_active));
      setSelectedDiscountId((current) => (
        result.data.discounts.some((discount) => discount.id === current && discount.is_active)
          ? current
          : ""
      ));
    }).catch((reason: unknown) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setDiscounts([]);
      setSelectedDiscountId("");
      setDiscountError("Не вдалося завантажити активні знижки.");
    }).finally(() => {
      if (!controller.signal.aborted) setIsLoadingDiscounts(false);
    });
    return () => { controller.abort(); };
  }, [discountLoadVersion]);

  useEffect(() => {
    let active = true;
    void apiClient.GET("/api/v1/services", {
      params: { query: { status: "active" } },
    }).then((result) => {
      if (!active) return;
      setIsLoadingServices(false);
      if (result.data === undefined) {
        setServices([]);
        setServiceIds([]);
        setError(result.error.message);
        return;
      }
      const activeServices = result.data.services.filter((service) => service.is_active !== false);
      const activeIds = new Set(activeServices.map((service) => service.id));
      setServices(activeServices);
      setServiceIds((current) => current.filter((serviceId) => activeIds.has(serviceId)));
    }).catch(() => {
      if (!active) return;
      setIsLoadingServices(false);
      setServices([]);
      setServiceIds([]);
      setError("Не вдалося завантажити активні послуги для наступного запису.");
    });
    return () => { active = false; };
  }, []);

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
    if (!scheduleFollowUp || followUpDate === "" || serviceIds.length === 0 || specialistId === "") {
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
          service_ids: [...serviceIds],
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
  }, [availabilityVersion, followUpDate, scheduleFollowUp, serviceIds, specialistId]);

  const followUpValid = !scheduleFollowUp || (
    followUpDate !== ""
    && serviceIds.length > 0
    && specialistId !== ""
    && startsAt !== ""
    && roomId !== ""
  );

  const submit = async () => {
    if (!confirmed || !followUpValid || isSubmitting) return;
    const body: MultiServiceFinishRequest = {
      version: visit.version,
      recommendations,
      payment_handoff_requested: handoffRequested,
      ...(selectedDiscount === undefined || totalMinor === 0
        ? {}
        : { discount_id: selectedDiscount.id }),
      follow_up: scheduleFollowUp ? {
        starts_at: startsAt,
        service_ids: [...serviceIds],
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
      if (result.error.code === "discount_unavailable") {
        setSelectedDiscountId("");
        setDiscountLoadVersion((current) => current + 1);
        setConfirmed(false);
        finishKey.current = crypto.randomUUID();
        setError("Обрана знижка вже недоступна. Каталог оновлено — перевірте суму та підтвердьте ще раз.");
        return;
      }
      setError(result.error.code === "insufficient_stock"
        ? "Залишок матеріалу змінився. Поверніться до кроку 2, оновіть партію або кількість і повторіть."
        : result.error.message);
      return;
    }
    onCompleted(result.data as FinishResult);
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

        <section className="visit-discount visit-finish-wide" aria-labelledby="visit-discount-title">
          <header>
            <div>
              <p className="eyebrow">Знижка · TP-1019</p>
              <h3 id="visit-discount-title">Розрахунок прийому</h3>
            </div>
            <span>{effectiveDiscount === null ? "Без знижки" : `${String(effectiveDiscount.percent)}%`}</span>
          </header>
          {visit.loyalty.is_active && visit.loyalty.visit_number !== null ? (
            <div
              className={`visit-loyalty-notice${loyaltyDiscount === null ? "" : " visit-loyalty-notice--active"}`}
              data-testid="visit-loyalty-notice"
              role="status"
            >
              <Icon name={loyaltyDiscount === null ? "settings" : "finance"} />
              {loyaltyDiscount === null ? (
                <span>
                  <strong>Це {visit.loyalty.visit_number}-й врахований візит пацієнта.</strong>
                  <small>Знижка постійного клієнта спрацює на кожен {visit.loyalty.every_n}-й візит.</small>
                </span>
              ) : (
                <span>
                  <strong>
                    {visit.loyalty.visit_number}-й візит — уже застосована знижка
                    постійного клієнта «{loyaltyDiscount.name}» {loyaltyDiscount.percent}%.
                  </strong>
                  <small>
                    Нічого робити не потрібно — вона застосується сама. Оберіть іншу знижку
                    нижче лише якщо хочете її замінити.
                  </small>
                </span>
              )}
            </div>
          ) : null}
          <div className="visit-discount__content">
            <label className="form-field">
              <span>{loyaltyDiscount === null ? "Ручна знижка" : "Замінити знижку"}</span>
              <select
                disabled={isSubmitting || isLoadingDiscounts || totalMinor === 0}
                onChange={(event) => {
                  setSelectedDiscountId(event.target.value);
                  markChanged();
                }}
                value={selectedDiscountId}
              >
                <option value="">{loyaltyDiscount === null
                  ? "Не застосовувати вручну"
                  : `Залишити знижку постійного клієнта · ${String(loyaltyDiscount.percent)}%`}</option>
                {discounts.map((discount) => (
                  <option key={discount.id} value={discount.id}>{discount.name} · {discount.percent}%</option>
                ))}
              </select>
              <small>{isLoadingDiscounts
                ? "Завантажуємо активні знижки…"
                : totalMinor === 0
                  ? "Для нульової вартості знижка не застосовується."
                  : "Сервер повторно перевірить активність знижки під час завершення."}</small>
            </label>
            <dl className="visit-discount__totals" aria-label="Попередній розрахунок">
              <div><dt>Вартість послуг</dt><dd>{money(totalMinor)}</dd></div>
              <div><dt>Знижка{effectiveDiscount === null ? "" : ` · ${effectiveDiscount.name}${loyaltyOverride !== null ? " (заміна)" : loyaltyDiscount === null ? "" : " (автоматична)"}`}</dt><dd>− {money(discountMinor)}</dd></div>
              <div><dt>До оплати</dt><dd>{money(netMinor)}</dd></div>
            </dl>
          </div>
          {discountError === null ? null : (
            <div className="visit-discount__error" role="status">
              <Icon name="warning" />
              <span>{discountError} Завершення без ручної знижки залишається доступним.</span>
              <button className="text-action" onClick={() => { setDiscountLoadVersion((current) => current + 1); }} type="button">Повторити</button>
            </div>
          )}
          {loyaltyOverride === null ? null : (
            <div
              className={`visit-discount__override${loyaltyOverride.downgrades ? " visit-discount__override--warning" : ""}`}
              data-testid="visit-loyalty-override"
              role="status"
            >
              <Icon name="warning" />
              <span>
                {loyaltyOverride.downgrades
                  ? `Ви замінюєте знижку постійного клієнта ${String(loyaltyOverride.loyalty.percent)}% на меншу ${String(loyaltyOverride.manual.percent)}%. Пацієнт отримає меншу знижку.`
                  : `Знижка постійного клієнта ${String(loyaltyOverride.loyalty.percent)}% буде замінена на «${loyaltyOverride.manual.name}» ${String(loyaltyOverride.manual.percent)}%.`}
              </span>
              <button className="text-action" onClick={() => { setSelectedDiscountId(""); markChanged(); }} type="button">
                Повернути знижку постійного клієнта
              </button>
            </div>
          )}
          <p className="visit-discount__hint">
            Знижки не сумуються: ручний вибір замінює знижку постійного клієнта.
            Остаточну суму сервер підтверджує атомарно під час завершення.
          </p>
        </section>

        <label className="form-field visit-finish-wide">
          <span>Рекомендації пацієнту · необов’язково</span>
          <textarea disabled={isSubmitting} maxLength={10000} onChange={(event) => { setRecommendations(event.target.value); markChanged(); }} placeholder="Домашній догляд, частота процедур, застереження" rows={5} value={recommendations} />
          <small>Рекомендації збережуться з автором і датою; ресепшн не бачить їх змісту.</small>
        </label>

        <label className="settings-check visit-finish-wide">
          <input checked={handoffRequested} disabled={isSubmitting} onChange={(event) => { setHandoffRequested(event.target.checked); markChanged(); }} type="checkbox" />
          <span><strong>Передати ресепшну на оплату</strong><small>Попередня сума до оплати: {money(netMinor)}. Саму оплату тут не проводимо.</small></span>
        </label>

        <fieldset className="visit-follow-up visit-finish-wide" disabled={isSubmitting}>
          <legend>Наступний запис</legend>
          <label className="settings-check">
            <input checked={scheduleFollowUp} onChange={(event) => { setScheduleFollowUp(event.target.checked); setStartsAt(""); setRoomId(""); markChanged(); }} type="checkbox" />
            <span><strong>Записати на наступний прийом</strong><small>У finish потраплять вибрані послуги та вільне вікно.</small></span>
          </label>
          {scheduleFollowUp ? (
            <div className="visit-follow-up__fields">
              <label className="form-field"><span>Дата</span><input min={todayInputValue()} onChange={(event) => { setFollowUpDate(event.target.value); markChanged(); }} type="date" value={followUpDate} /></label>
              <ServiceMultiSelect
                isLoading={isLoadingServices}
                onChange={(nextServiceIds) => {
                  setServiceIds(nextServiceIds);
                  setStartsAt("");
                  setRoomId("");
                  setAvailability(null);
                  setAvailabilityState("idle");
                  setAvailabilityError(null);
                  markChanged();
                }}
                selectedIds={serviceIds}
                services={services}
              />
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
        <div><strong>Попередньо до оплати: {money(netMinor)}</strong><small>Authoritative pricing поверне сервер після loyalty та locked validation.</small></div>
        <div>
          <button className="button button--secondary" disabled={isSubmitting} onClick={onBack} type="button">Назад до фото</button>
          <button className="button button--primary" disabled={!confirmed || !followUpValid || isSubmitting} onClick={() => { void submit(); }} type="button">{isSubmitting ? "Завершуємо…" : handoffRequested ? "Завершити й передати на оплату" : "Завершити прийом"}</button>
        </div>
      </footer>
    </section>
  );
}

export type { FinishResult };
