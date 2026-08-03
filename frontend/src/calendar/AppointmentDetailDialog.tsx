import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type SyntheticEvent,
} from "react";

import { apiClient } from "../api/client";
import type { components, operations } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";
import { ServiceMultiSelect } from "./ServiceMultiSelect";

type Appointment = components["schemas"]["AppointmentDetailResponse"];
type AppointmentUpdate = NonNullable<operations["appointment_update"]["requestBody"]>["content"]["application/json"];
type Availability = components["schemas"]["AvailabilityResponse"];
type Service = components["schemas"]["Service"];
type Specialist = components["schemas"]["SpecialistSummary"];
type StatusCode = components["schemas"]["AppointmentStatusTransitionStatusCodeEnum"];
type FieldErrors = Readonly<Record<string, readonly string[]>>;
type EditorMode = "view" | "edit" | "reschedule" | "cancel";

interface AppointmentDetailDialogProps {
  readonly appointmentId: string;
  readonly onChanged: (appointment: Appointment, message: string) => void;
  readonly onClose: () => void;
  readonly onVisitOpened: (visitId: string) => void;
  readonly specialists: readonly Specialist[];
}

const dateTimeFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  weekday: "short",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const timeFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function localDateKey(value: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Kyiv",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  return `${pick("year")}-${pick("month")}-${pick("day")}`;
}

function fieldMessage(errors: FieldErrors, field: string): string | null {
  return errors[field]?.[0] ?? null;
}

function modeTitle(mode: EditorMode): string {
  if (mode === "edit") return "Редагування запису";
  if (mode === "reschedule") return "Перенесення запису";
  if (mode === "cancel") return "Скасування запису";
  return "Деталі запису";
}

export function AppointmentDetailDialog({
  appointmentId,
  onChanged,
  onClose,
  onVisitOpened,
  specialists,
}: AppointmentDetailDialogProps) {
  const [appointment, setAppointment] = useState<Appointment | null>(null);
  const [mode, setMode] = useState<EditorMode>("view");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isUnavailable, setIsUnavailable] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [services, setServices] = useState<readonly Service[]>([]);
  const [complaints, setComplaints] = useState("");
  const [hasNoComplaints, setHasNoComplaints] = useState(false);
  const [comment, setComment] = useState("");
  const [specialistId, setSpecialistId] = useState("");
  const [serviceIds, setServiceIds] = useState<readonly string[]>([]);
  const [date, setDate] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [roomId, setRoomId] = useState("");
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [isLoadingAvailability, setIsLoadingAvailability] = useState(false);
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [availabilityVersion, setAvailabilityVersion] = useState(0);
  const [cancelReason, setCancelReason] = useState("");
  const selectedServices = serviceIds.flatMap((id) => {
    const service = services.find((item) => item.id === id);
    return service === undefined ? [] : [service];
  });
  const totalDuration = selectedServices.reduce(
    (total, service) => total + service.duration_minutes,
    0,
  );
  const selectedSlot = availability?.slots.find((slot) => slot.starts_at === startsAt);

  const resetForms = useCallback((value: Appointment) => {
    setComplaints(value.complaints);
    setHasNoComplaints(value.has_no_complaints);
    setComment(value.comment);
    setSpecialistId(String(value.specialist.id));
    setServiceIds(value.services.map((service) => service.id));
    setDate(localDateKey(value.starts_at));
    setStartsAt("");
    setRoomId("");
    setAvailability(null);
    setAvailabilityError(null);
    setCancelReason("");
    setFieldErrors({});
  }, []);

  const loadAppointment = useCallback(async (showLoader = true) => {
    if (showLoader) {
      setIsLoading(true);
      setAppointment(null);
    }
    setError(null);
    setIsUnavailable(false);
    const result = await apiClient.GET("/api/v1/appointments/{appointment_id}", {
      params: { path: { appointment_id: appointmentId } },
    }).catch(() => null);
    if (showLoader) setIsLoading(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Перевірте мережу й повторіть спробу.");
      return null;
    }
    if (result.data === undefined) {
      const unavailable = result.response.status === 403 || result.response.status === 404;
      setIsUnavailable(unavailable);
      setError(unavailable
        ? "Запис не знайдено або він недоступний у межах вашої ролі."
        : result.error.message);
      return null;
    }
    setAppointment(result.data);
    if (showLoader) resetForms(result.data);
    return result.data;
  }, [appointmentId, resetForms]);

  useEffect(() => {
    void loadAppointment();
  }, [loadAppointment]);

  useEffect(() => {
    const loadServices = async () => {
      const result = await apiClient.GET("/api/v1/services", {
        params: { query: { status: "active" } },
      }).catch(() => null);
      if (result?.data !== undefined) setServices(result.data.services);
    };
    void loadServices();
  }, []);

  useEffect(() => {
    if (mode !== "reschedule") return;
    const parsedSpecialistId = Number(specialistId);
    if (serviceIds.length === 0 || !date || !Number.isInteger(parsedSpecialistId)) {
      setAvailability(null);
      return;
    }
    let active = true;
    setIsLoadingAvailability(true);
    setAvailabilityError(null);
    void apiClient.GET("/api/v1/appointments/availability", {
      params: {
        query: {
          date,
          specialist_id: parsedSpecialistId,
          service_ids: [...serviceIds],
        },
      },
    }).then((result) => {
      if (!active) return;
      setIsLoadingAvailability(false);
      if (result.data === undefined) {
        setAvailability(null);
        setAvailabilityError(result.error.message);
        return;
      }
      setAvailability(result.data);
    }).catch(() => {
      if (!active) return;
      setIsLoadingAvailability(false);
      setAvailability(null);
      setAvailabilityError("Не вдалося перевірити вільні вікна.");
    });
    return () => { active = false; };
  }, [availabilityVersion, date, mode, serviceIds, specialistId]);

  const clearMessages = () => {
    setError(null);
    setFieldErrors({});
  };

  const acceptMutation = (value: Appointment, message: string) => {
    setAppointment(value);
    resetForms(value);
    setMode("view");
    setError(null);
    setIsSaving(false);
    onChanged(value, message);
  };

  const handleFailure = async (
    result: { readonly error?: { readonly code: string; readonly message: string; readonly fields: FieldErrors } } | null,
  ) => {
    setIsSaving(false);
    if (result?.error === undefined) {
      setError("Немає зв’язку із сервером. Введені дані залишилися у формі.");
      return;
    }
    setError(result.error.message);
    setFieldErrors(result.error.fields);
    if (result.error.code === "appointment_slot_conflict") {
      setStartsAt("");
      setRoomId("");
      setAvailabilityVersion((current) => current + 1);
    }
    if (result.error.code === "appointment_version_conflict") {
      await loadAppointment(false);
    }
  };

  const submitEdit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (appointment === null) return;
    if (hasNoComplaints === Boolean(complaints.trim())) {
      setFieldErrors({ complaints: ["Укажіть скарги або виберіть «Скарг немає»."] });
      setError("Перевірте обов’язкові поля форми.");
      return;
    }
    setIsSaving(true);
    clearMessages();
    const body: AppointmentUpdate = {
      version: appointment.version,
      complaints,
      has_no_complaints: hasNoComplaints,
      comment,
    };
    const result = await apiClient.PATCH("/api/v1/appointments/{appointment_id}", {
      params: { path: { appointment_id: appointment.id } },
      body,
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result?.data === undefined) {
      await handleFailure(result);
      return;
    }
    acceptMutation(result.data, `Запис ${result.data.public_number} оновлено.`);
  };

  const submitReschedule = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (appointment === null) return;
    const parsedSpecialistId = Number(specialistId);
    const localErrors: Record<string, string[]> = {};
    if (!Number.isInteger(parsedSpecialistId)) localErrors.specialist_id = ["Оберіть спеціаліста."];
    if (serviceIds.length === 0) localErrors.service_ids = ["Оберіть хоча б одну послугу."];
    if (!startsAt) localErrors.starts_at = ["Оберіть нове вільне вікно."];
    if (!roomId) localErrors.room_id = ["Оберіть кабінет."];
    if (Object.keys(localErrors).length > 0) {
      setFieldErrors(localErrors);
      setError("Перевірте обов’язкові поля форми.");
      return;
    }
    setIsSaving(true);
    clearMessages();
    const result = await apiClient.PATCH("/api/v1/appointments/{appointment_id}", {
      params: { path: { appointment_id: appointment.id } },
      body: {
        version: appointment.version,
        specialist_id: parsedSpecialistId,
        service_ids: [...serviceIds],
        room_id: roomId,
        starts_at: startsAt,
      },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result?.data === undefined) {
      await handleFailure(result);
      return;
    }
    acceptMutation(result.data, `Запис ${result.data.public_number} перенесено.`);
  };

  const applyStatus = async (statusCode: StatusCode) => {
    if (appointment === null) return;
    setIsSaving(true);
    clearMessages();
    const result = await apiClient.POST("/api/v1/appointments/{appointment_id}/status", {
      params: { path: { appointment_id: appointment.id } },
      body: { version: appointment.version, status_code: statusCode },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result?.data === undefined) {
      await handleFailure(result);
      return;
    }
    acceptMutation(result.data, `Статус запису змінено на «${result.data.status.label}».`);
  };

  const submitCancel = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (appointment === null) return;
    if (!cancelReason.trim()) {
      setFieldErrors({ reason: ["Укажіть причину скасування."] });
      return;
    }
    setIsSaving(true);
    clearMessages();
    const result = await apiClient.POST("/api/v1/appointments/{appointment_id}/cancel", {
      params: { path: { appointment_id: appointment.id } },
      body: { version: appointment.version, reason: cancelReason },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result?.data === undefined) {
      await handleFailure(result);
      return;
    }
    acceptMutation(result.data, `Запис ${result.data.public_number} скасовано.`);
  };

  const openVisit = async () => {
    if (appointment === null) return;
    if (appointment.visit_id !== null) {
      onVisitOpened(appointment.visit_id);
      return;
    }
    setIsSaving(true);
    clearMessages();
    const result = await apiClient.POST("/api/v1/appointments/{appointment_id}/start-visit", {
      params: { path: { appointment_id: appointment.id } },
      body: { version: appointment.version },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result?.data === undefined) {
      await handleFailure(result);
      return;
    }
    setIsSaving(false);
    onVisitOpened(result.data.id);
  };

  const currentFingerprint = useMemo(() => JSON.stringify({ complaints, hasNoComplaints, comment }), [comment, complaints, hasNoComplaints]);
  const savedFingerprint = appointment === null ? "" : JSON.stringify({
    complaints: appointment.complaints,
    hasNoComplaints: appointment.has_no_complaints,
    comment: appointment.comment,
  });
  const editChanged = currentFingerprint !== savedFingerprint;

  return (
    <div className="modal-layer" role="presentation">
      <section aria-labelledby="appointment-detail-title" aria-modal="true" className="modal-card appointment-detail" role="dialog">
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Календар · TP-403</p>
            <h2 id="appointment-detail-title">{modeTitle(mode)}</h2>
            <p>{appointment?.public_number ?? "Завантажуємо актуальні дані…"}</p>
          </div>
          <button aria-label="Закрити деталі запису" autoFocus className="icon-button" disabled={isSaving} onClick={onClose} type="button"><Icon name="close" /></button>
        </header>

        {isLoading ? <div className="appointment-detail__loading" role="status"><span className="spinner" aria-hidden="true" />Завантажуємо запис…</div> : null}
        {!isLoading && appointment === null ? <div className="form-message form-message--error appointment-detail__error" role="alert"><Icon name="warning" /><span>{error ?? "Запис не знайдено."}</span>{isUnavailable ? null : <button className="text-action" onClick={() => { void loadAppointment(); }} type="button">Повторити</button>}</div> : null}

        {!isLoading && appointment !== null && mode === "view" ? (
          <div className="appointment-detail__body">
            <div className="appointment-detail__patient">
              <span className="avatar avatar--sage" aria-hidden="true">{appointment.patient.display_name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("")}</span>
              <span><strong>{appointment.patient.display_name}</strong><small>{appointment.patient.public_number} · {appointment.patient.phone}</small></span>
              <span className="appointment-detail__status" style={{ "--status-color": appointment.status.color } as CSSProperties}>{appointment.status.label}</span>
            </div>
            <dl className="appointment-detail__facts">
              <div><dt>Дата й час</dt><dd>{dateTimeFormatter.format(new Date(appointment.starts_at))}–{timeFormatter.format(new Date(appointment.ends_at))}</dd></div>
              <div className="appointment-detail__wide"><dt>Послуги</dt><dd className="appointment-detail__services">{appointment.services.map((service) => <span key={service.id} style={{ "--service-color": service.color } as CSSProperties}><i aria-hidden="true" />{service.name}<small>{service.duration_minutes} хв</small></span>)}<strong>Разом: {appointment.duration_minutes} хв</strong></dd></div>
              <div><dt>Спеціаліст</dt><dd>{appointment.specialist.display_name}</dd></div>
              <div><dt>Кабінет</dt><dd>{appointment.room.name}</dd></div>
              <div className="appointment-detail__wide"><dt>Скарги</dt><dd>{appointment.has_no_complaints ? "Скарг немає" : appointment.complaints}</dd></div>
              <div className="appointment-detail__wide"><dt>Коментар</dt><dd>{appointment.comment || "Не додано"}</dd></div>
              {appointment.cancellation_reason ? <div className="appointment-detail__wide appointment-detail__cancel-note"><dt>Причина скасування</dt><dd>{appointment.cancellation_reason}</dd></div> : null}
            </dl>

            {error ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
            {appointment.allowed_status_transitions.length > 0 ? (
              <section className="appointment-status-actions" aria-label="Доступні зміни статусу">
                <h3>Наступна дія</h3>
                <div>{appointment.allowed_status_transitions.map((status) => <button className="appointment-status-button" disabled={isSaving} key={status.code} onClick={() => { void applyStatus(status.code as StatusCode); }} style={{ "--status-color": status.color } as CSSProperties} type="button">{status.label}</button>)}</div>
              </section>
            ) : null}
            <div className="modal-actions appointment-detail__actions">
              {appointment.can_cancel ? <button className="button button--danger-ghost" disabled={isSaving} onClick={() => { clearMessages(); setMode("cancel"); }} type="button">Скасувати запис</button> : null}
              <span />
              {appointment.visit_id !== null ? <button className="button button--primary" disabled={isSaving} onClick={() => { void openVisit(); }} type="button">Продовжити прийом</button> : null}
              {appointment.can_start_visit ? <button className="button button--primary" disabled={isSaving} onClick={() => { void openVisit(); }} type="button">{isSaving ? "Починаємо…" : "Почати прийом"}</button> : null}
              {appointment.can_edit ? <button className="button button--secondary" onClick={() => { resetForms(appointment); setMode("edit"); }} type="button">Редагувати</button> : null}
              {appointment.can_reschedule ? <button className="button button--primary" onClick={() => { resetForms(appointment); setMode("reschedule"); }} type="button">Перенести</button> : null}
              {!appointment.can_edit && !appointment.can_reschedule ? <button className="button button--secondary" onClick={onClose} type="button">Закрити</button> : null}
            </div>
          </div>
        ) : null}

        {!isLoading && appointment !== null && mode === "edit" ? (
          <form onSubmit={(event) => void submitEdit(event)}>
            <div className="appointment-form-grid">
              <label className="form-field appointment-form-wide"><span>Скарги / причина звернення</span><textarea disabled={hasNoComplaints} maxLength={4000} onChange={(event) => { setComplaints(event.target.value); clearMessages(); }} rows={4} value={complaints} />{fieldMessage(fieldErrors, "complaints") ? <small className="field-error">{fieldMessage(fieldErrors, "complaints")}</small> : null}</label>
              <label className="settings-check appointment-form-wide"><input aria-label="Скарг немає" checked={hasNoComplaints} onChange={(event) => { setHasNoComplaints(event.target.checked); if (event.target.checked) setComplaints(""); clearMessages(); }} type="checkbox" /><span><strong>Скарг немає</strong><small>Явне підтвердження для профілактичного візиту.</small></span></label>
              <label className="form-field appointment-form-wide"><span>Коментар · необов’язково</span><textarea maxLength={4000} onChange={(event) => { setComment(event.target.value); clearMessages(); }} rows={3} value={comment} /></label>
            </div>
            {error ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
            <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={() => { resetForms(appointment); setMode("view"); }} type="button">Назад</button><button className="button button--primary" disabled={isSaving || !editChanged} type="submit">{isSaving ? "Зберігаємо…" : "Зберегти зміни"}</button></div>
          </form>
        ) : null}

        {!isLoading && appointment !== null && mode === "reschedule" ? (
          <form onSubmit={(event) => void submitReschedule(event)}>
            <div className="appointment-current-slot"><Icon name="calendar" /><span><strong>Поточний час</strong><small>{dateTimeFormatter.format(new Date(appointment.starts_at))} · {appointment.room.name}</small></span></div>
            <div className="appointment-form-grid">
              <label className="form-field"><span>Спеціаліст</span><select onChange={(event) => { setSpecialistId(event.target.value); setStartsAt(""); setRoomId(""); clearMessages(); }} value={specialistId}>{specialists.map((specialist) => <option key={specialist.id} value={specialist.id}>{specialist.display_name}</option>)}</select>{fieldMessage(fieldErrors, "specialist_id") ? <small className="field-error">{fieldMessage(fieldErrors, "specialist_id")}</small> : null}</label>
              <ServiceMultiSelect
                error={fieldMessage(fieldErrors, "service_ids") ?? fieldMessage(fieldErrors, "service_id")}
                onChange={(nextServiceIds) => {
                  setServiceIds(nextServiceIds);
                  setStartsAt("");
                  setRoomId("");
                  clearMessages();
                }}
                selectedIds={serviceIds}
                services={services}
              />
              <label className="form-field"><span>Нова дата</span><input onChange={(event) => { setDate(event.target.value); setStartsAt(""); setRoomId(""); clearMessages(); }} required type="date" value={date} /></label>
              <label className="form-field"><span>Тривалість</span><input readOnly value={totalDuration > 0 ? `${String(totalDuration)} хв` : "—"} /></label>
              <label className="form-field"><span>Новий час</span><select disabled={isLoadingAvailability || availability === null} onChange={(event) => { const value = event.target.value; setStartsAt(value); const slot = availability?.slots.find((item) => item.starts_at === value); setRoomId(slot?.rooms[0]?.id ?? ""); clearMessages(); }} value={startsAt}><option value="">{isLoadingAvailability ? "Перевіряємо…" : "Оберіть час"}</option>{availability?.slots.map((slot) => <option key={slot.starts_at} value={slot.starts_at}>{timeFormatter.format(new Date(slot.starts_at))}–{timeFormatter.format(new Date(slot.ends_at))}</option>)}</select>{fieldMessage(fieldErrors, "starts_at") ? <small className="field-error">{fieldMessage(fieldErrors, "starts_at")}</small> : null}</label>
              <label className="form-field"><span>Кабінет</span><select disabled={!selectedSlot} onChange={(event) => { setRoomId(event.target.value); clearMessages(); }} value={roomId}><option value="">Оберіть кабінет</option>{selectedSlot?.rooms.map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}</select>{fieldMessage(fieldErrors, "room_id") ? <small className="field-error">{fieldMessage(fieldErrors, "room_id")}</small> : null}</label>
            </div>
            {availabilityError ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{availabilityError}</span></div> : null}
            {error ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
            <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={() => { resetForms(appointment); setMode("view"); }} type="button">Назад</button><button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Переносимо…" : "Підтвердити перенесення"}</button></div>
          </form>
        ) : null}

        {!isLoading && appointment !== null && mode === "cancel" ? (
          <form onSubmit={(event) => void submitCancel(event)}>
            <div className="appointment-cancel-warning"><Icon name="warning" /><span><strong>Скасування звільнить це вікно</strong><small>Запис залишиться в історії та audit trail. Відновити його зміною статусу буде неможливо.</small></span></div>
            <label className="form-field"><span>Причина скасування · обов’язково</span><textarea autoFocus maxLength={1000} onChange={(event) => { setCancelReason(event.target.value); clearMessages(); }} rows={4} value={cancelReason} />{fieldMessage(fieldErrors, "reason") ? <small className="field-error">{fieldMessage(fieldErrors, "reason")}</small> : null}</label>
            {error ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
            <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={() => { setCancelReason(""); setMode("view"); clearMessages(); }} type="button">Назад</button><button className="button button--danger" disabled={isSaving} type="submit">{isSaving ? "Скасовуємо…" : "Скасувати запис"}</button></div>
          </form>
        ) : null}
      </section>
    </div>
  );
}
