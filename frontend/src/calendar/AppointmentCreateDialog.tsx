import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type SyntheticEvent,
} from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders, useAuth } from "../auth/AuthContext";
import { PatientCreateDialog } from "../patients/PatientsPage";
import { ServiceMultiSelect } from "./ServiceMultiSelect";

type Appointment = components["schemas"]["AppointmentResponse"];
type AppointmentCreateRequest = components["schemas"]["AppointmentCreateRequest"];
type Availability = components["schemas"]["AvailabilityResponse"];
type Patient = components["schemas"]["PatientListItem"];
type PatientDetail = components["schemas"]["PatientDetailResponse"];
type Service = components["schemas"]["Service"];
type Specialist = components["schemas"]["SpecialistSummary"];
type FieldErrors = Readonly<Record<string, readonly string[]>>;

interface SlotPreset {
  readonly specialistId: number;
  readonly startsAt: string;
}

interface AppointmentPatient {
  readonly id: string;
  readonly public_number: string;
  readonly display_name: string;
  readonly phone: string;
}

interface AppointmentCreateDialogProps {
  readonly initialDate: string;
  readonly onClose: () => void;
  readonly onSaved: (appointment: Appointment) => void;
  readonly presetPatientId?: string;
  readonly presetSlot?: SlotPreset | null;
  readonly specialists: readonly Specialist[];
}

function patientReference(patient: Patient | PatientDetail): AppointmentPatient {
  return {
    id: patient.id,
    public_number: patient.public_number,
    display_name: patient.display_name,
    phone: patient.phone,
  };
}

function fieldMessage(errors: FieldErrors, field: string): string | null {
  return errors[field]?.[0] ?? null;
}

function dateTimeLabel(value: string): string {
  return new Intl.DateTimeFormat("uk-UA", {
    timeZone: "Europe/Kyiv",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function AppointmentCreateDialog({
  initialDate,
  onClose,
  onSaved,
  presetPatientId,
  presetSlot,
  specialists,
}: AppointmentCreateDialogProps) {
  const { state } = useAuth();
  const isPodologist = state.status === "authenticated"
    && state.session.user.role === "podologist";
  const ownSpecialistId = state.status === "authenticated" ? state.session.user.id : 0;
  const initialSpecialistId = presetSlot?.specialistId
    ?? (isPodologist ? ownSpecialistId : specialists.length === 1 ? specialists[0]?.id : undefined);
  const [selectedPatient, setSelectedPatient] = useState<AppointmentPatient | null>(null);
  const [patientSearch, setPatientSearch] = useState("");
  const [patientResults, setPatientResults] = useState<readonly Patient[]>([]);
  const [isSearchingPatients, setIsSearchingPatients] = useState(false);
  const [isLoadingPresetPatient, setIsLoadingPresetPatient] = useState(Boolean(presetPatientId));
  const [isCreatingPatient, setIsCreatingPatient] = useState(false);
  const [services, setServices] = useState<readonly Service[]>([]);
  const [isLoadingServices, setIsLoadingServices] = useState(true);
  const [specialistId, setSpecialistId] = useState(
    initialSpecialistId === undefined ? "" : String(initialSpecialistId),
  );
  const [serviceIds, setServiceIds] = useState<readonly string[]>([]);
  const [date, setDate] = useState(initialDate);
  const [startsAt, setStartsAt] = useState("");
  const [roomId, setRoomId] = useState("");
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [availabilityVersion, setAvailabilityVersion] = useState(0);
  const [isLoadingAvailability, setIsLoadingAvailability] = useState(false);
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [complaints, setComplaints] = useState("");
  const [hasNoComplaints, setHasNoComplaints] = useState(false);
  const [comment, setComment] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [confirmClose, setConfirmClose] = useState(false);
  const presetSlotPending = useRef(presetSlot !== null && presetSlot !== undefined);
  const selectedServices = serviceIds.flatMap((id) => {
    const service = services.find((item) => item.id === id);
    return service === undefined ? [] : [service];
  });
  const totalDuration = selectedServices.reduce(
    (total, service) => total + service.duration_minutes,
    0,
  );
  const selectedSlot = availability?.slots.find((slot) => slot.starts_at === startsAt);
  const fingerprint = JSON.stringify({
    patientId: selectedPatient?.id ?? null,
    specialistId,
    serviceIds,
    date,
    startsAt,
    roomId,
    complaints,
    hasNoComplaints,
    comment,
  });
  const initialFingerprint = useMemo(() => JSON.stringify({
    patientId: presetPatientId ?? null,
    specialistId: initialSpecialistId === undefined ? "" : String(initialSpecialistId),
    serviceIds: [],
    date: initialDate,
    startsAt: "",
    roomId: "",
    complaints: "",
    hasNoComplaints: false,
    comment: "",
  }), [initialDate, initialSpecialistId, presetPatientId]);

  const clearMessages = () => {
    setError(null);
    setFieldErrors({});
    setConfirmClose(false);
  };

  useEffect(() => {
    const loadServices = async () => {
      const result = await apiClient.GET("/api/v1/services", {
        params: { query: { status: "active" } },
      }).catch(() => null);
      setIsLoadingServices(false);
      if (result?.data === undefined) {
        setError(result?.error.message ?? "Не вдалося завантажити послуги.");
        return;
      }
      setServices(result.data.services.filter((service) => service.is_active !== false));
    };
    void loadServices();
  }, []);

  useEffect(() => {
    if (!presetPatientId) return;
    const loadPatient = async () => {
      const result = await apiClient.GET("/api/v1/patients/{patient_id}", {
        params: { path: { patient_id: presetPatientId } },
      }).catch(() => null);
      setIsLoadingPresetPatient(false);
      if (result?.data === undefined) {
        setError(result?.error.message ?? "Не вдалося завантажити пацієнта.");
        return;
      }
      setSelectedPatient(patientReference(result.data));
    };
    void loadPatient();
  }, [presetPatientId]);

  useEffect(() => {
    if (presetPatientId || patientSearch.trim().length < 2) {
      setPatientResults([]);
      setIsSearchingPatients(false);
      return;
    }
    setIsSearchingPatients(true);
    const timeout = window.setTimeout(() => {
      void apiClient.GET("/api/v1/patients", {
        params: { query: { search: patientSearch.trim() } },
      }).then((result) => {
        setPatientResults(result.data?.patients ?? []);
        setIsSearchingPatients(false);
      }).catch(() => {
        setPatientResults([]);
        setIsSearchingPatients(false);
      });
    }, 250);
    return () => { window.clearTimeout(timeout); };
  }, [patientSearch, presetPatientId]);

  useEffect(() => {
    const parsedSpecialistId = Number(specialistId);
    if (serviceIds.length === 0 || !Number.isInteger(parsedSpecialistId) || parsedSpecialistId < 1 || !date) {
      setAvailability(null);
      setIsLoadingAvailability(false);
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
      if (presetSlotPending.current && presetSlot) {
        presetSlotPending.current = false;
        const presetTimestamp = new Date(presetSlot.startsAt).getTime();
        const matching = result.data.slots.find(
          (slot) => new Date(slot.starts_at).getTime() === presetTimestamp,
        );
        if (matching) {
          setStartsAt(matching.starts_at);
          setRoomId(matching.rooms[0]?.id ?? "");
        } else {
          setAvailabilityError("Попередньо вибране вікно не підходить для цієї послуги.");
        }
      }
    }).catch(() => {
      if (active) {
        setAvailability(null);
        setIsLoadingAvailability(false);
        setAvailabilityError("Не вдалося перевірити вільні вікна.");
      }
    });
    return () => { active = false; };
  }, [availabilityVersion, date, presetSlot, serviceIds, specialistId]);

  const requestClose = () => {
    if (fingerprint !== initialFingerprint) {
      setConfirmClose(true);
      return;
    }
    onClose();
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedSpecialistId = Number(specialistId);
    const localErrors: Record<string, string[]> = {};
    if (!selectedPatient) localErrors.patient_id = ["Оберіть пацієнта."];
    if (!Number.isInteger(parsedSpecialistId) || parsedSpecialistId < 1) {
      localErrors.specialist_id = ["Оберіть спеціаліста."];
    }
    if (serviceIds.length === 0) localErrors.service_ids = ["Оберіть хоча б одну послугу."];
    if (!startsAt) localErrors.starts_at = ["Оберіть вільний час."];
    if (!roomId) localErrors.room_id = ["Оберіть доступний кабінет."];
    if (hasNoComplaints === Boolean(complaints.trim())) {
      localErrors.complaints = ["Укажіть скарги або виберіть «Скарг немає»."];
    }
    if (Object.keys(localErrors).length > 0) {
      setFieldErrors(localErrors);
      setError("Перевірте обов’язкові поля форми.");
      return;
    }

    setIsSaving(true);
    setError(null);
    setFieldErrors({});
    const body: AppointmentCreateRequest = {
      patient_id: selectedPatient?.id ?? "",
      specialist_id: parsedSpecialistId,
      service_ids: [...serviceIds],
      room_id: roomId,
      starts_at: startsAt,
      complaints,
      has_no_complaints: hasNoComplaints,
      comment,
      status_code: "NEW",
    };
    const result = await apiClient.POST("/api/v1/appointments", {
      body,
      headers: csrfHeaders(),
    }).catch(() => null);
    setIsSaving(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Введені дані збережено у формі.");
      return;
    }
    if (result.data === undefined) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
      if (result.error.code === "appointment_slot_conflict") {
        setStartsAt("");
        setRoomId("");
        setAvailabilityVersion((current) => current + 1);
      }
      return;
    }
    onSaved(result.data);
  };

  return (
    <div className="modal-layer" role="presentation">
      <section aria-labelledby="appointment-create-title" aria-modal="true" className="modal-card appointment-editor" role="dialog">
        <header className="modal-card__header">
          <div><p className="eyebrow">Календар · TP-402</p><h2 id="appointment-create-title">Новий запис</h2><p>Вільний час перевіряється для спеціаліста й кабінету перед збереженням.</p></div>
          <button aria-label="Закрити форму запису" className="icon-button" onClick={requestClose} type="button"><Icon name="close" /></button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="appointment-form-grid">
            <div className="appointment-form-wide appointment-patient-field">
              <span>Пацієнт · обов’язково</span>
              {isLoadingPresetPatient ? <div className="appointment-inline-loading" role="status">Завантажуємо пацієнта…</div> : null}
              {selectedPatient ? (
                <div className="work-item-selected-patient">
                  <span><strong>{selectedPatient.display_name}</strong><small>{selectedPatient.public_number} · {selectedPatient.phone}</small></span>
                  {presetPatientId ? <span className="appointment-lock"><Icon name="lock" /> Пацієнта зафіксовано</span> : <button className="text-action" onClick={() => { setSelectedPatient(null); clearMessages(); }} type="button">Змінити</button>}
                </div>
              ) : presetPatientId ? null : (
                <>
                  <label className="patient-search"><Icon name="search" /><span className="visually-hidden">Знайти пацієнта для запису</span><input autoFocus onChange={(event) => { setPatientSearch(event.target.value); clearMessages(); }} placeholder="Ім’я, телефон або № пацієнта" type="search" value={patientSearch} /></label>
                  {isSearchingPatients ? <small>Шукаємо пацієнта…</small> : null}
                  {patientResults.length > 0 ? <div className="work-item-patient-results">{patientResults.map((patient) => <button key={patient.id} onClick={() => { setSelectedPatient(patientReference(patient)); setPatientSearch(""); setPatientResults([]); clearMessages(); }} type="button"><strong>{patient.display_name}</strong><small>{patient.public_number} · {patient.phone}</small></button>)}</div> : null}
                  {patientSearch.trim().length >= 2 && !isSearchingPatients && patientResults.length === 0 ? <div className="appointment-patient-empty"><span>Пацієнта не знайдено.</span><button className="button button--secondary" onClick={() => { setIsCreatingPatient(true); }} type="button"><Icon name="plus" />Створити пацієнта</button></div> : null}
                </>
              )}
              {fieldMessage(fieldErrors, "patient_id") ? <small className="field-error">{fieldMessage(fieldErrors, "patient_id")}</small> : null}
            </div>

            <label className="form-field"><span>Спеціаліст</span><select aria-label="Спеціаліст" disabled={isPodologist} onChange={(event) => { presetSlotPending.current = false; setSpecialistId(event.target.value); setStartsAt(""); setRoomId(""); clearMessages(); }} value={specialistId}><option value="">Оберіть спеціаліста</option>{specialists.map((specialist) => <option key={specialist.id} value={specialist.id}>{specialist.display_name}</option>)}</select>{isPodologist ? <small>Подолог створює запис лише до себе.</small> : null}{fieldMessage(fieldErrors, "specialist_id") ? <small className="field-error">{fieldMessage(fieldErrors, "specialist_id")}</small> : null}</label>
            <ServiceMultiSelect
              error={fieldMessage(fieldErrors, "service_ids") ?? fieldMessage(fieldErrors, "service_id")}
              isLoading={isLoadingServices}
              onChange={(nextServiceIds) => {
                setServiceIds(nextServiceIds);
                setStartsAt("");
                setRoomId("");
                clearMessages();
              }}
              selectedIds={serviceIds}
              services={services}
            />
            <label className="form-field"><span>Дата</span><input onChange={(event) => { presetSlotPending.current = false; setDate(event.target.value); setStartsAt(""); setRoomId(""); clearMessages(); }} required type="date" value={date} /></label>
            <label className="form-field"><span>Тривалість</span><input readOnly value={totalDuration > 0 ? `${String(totalDuration)} хв` : "Оберіть послуги"} /></label>
            <label className="form-field"><span>Вільний час</span><select disabled={isLoadingAvailability || availability === null} onChange={(event) => { const value = event.target.value; setStartsAt(value); const slot = availability?.slots.find((item) => item.starts_at === value); setRoomId(slot?.rooms[0]?.id ?? ""); clearMessages(); }} value={startsAt}><option value="">{isLoadingAvailability ? "Перевіряємо…" : "Оберіть час"}</option>{availability?.slots.map((slot) => <option key={slot.starts_at} value={slot.starts_at}>{dateTimeLabel(slot.starts_at)}–{dateTimeLabel(slot.ends_at)}</option>)}</select>{fieldMessage(fieldErrors, "starts_at") ? <small className="field-error">{fieldMessage(fieldErrors, "starts_at")}</small> : null}</label>
            <label className="form-field"><span>Кабінет</span><select disabled={!selectedSlot} onChange={(event) => { setRoomId(event.target.value); clearMessages(); }} value={roomId}><option value="">Оберіть кабінет</option>{selectedSlot?.rooms.map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}</select>{fieldMessage(fieldErrors, "room_id") ? <small className="field-error">{fieldMessage(fieldErrors, "room_id")}</small> : null}</label>
            <label className="form-field"><span>Статус</span><input aria-label="Статус" readOnly value="Новий" /><small>Початковий системний статус.</small></label>
            <div className="form-field"><span>Доступність</span><div className={`appointment-availability-state ${availabilityError ? "appointment-availability-state--error" : ""}`}>{isLoadingAvailability ? "Перевіряємо графік…" : availabilityError ?? (availability ? availability.slots.length > 0 ? `Вільних вікон: ${String(availability.slots.length)}` : "Вільних вікон немає" : "Оберіть спеціаліста, послуги й дату")}</div></div>

            <label className="form-field appointment-form-wide"><span>Скарги / причина звернення</span><textarea disabled={hasNoComplaints} maxLength={4000} onChange={(event) => { setComplaints(event.target.value); clearMessages(); }} placeholder="Опишіть скарги або причину звернення" rows={3} value={complaints} />{fieldMessage(fieldErrors, "complaints") ? <small className="field-error">{fieldMessage(fieldErrors, "complaints")}</small> : null}</label>
            <label className="settings-check appointment-form-wide"><input aria-label="Скарг немає" checked={hasNoComplaints} onChange={(event) => { const checked = event.target.checked; setHasNoComplaints(checked); if (checked) setComplaints(""); clearMessages(); }} type="checkbox" /><span><strong>Скарг немає</strong><small>Явно підтвердіть відсутність скарг для профілактичної послуги.</small></span></label>
            <label className="form-field appointment-form-wide"><span>Коментар · необов’язково</span><textarea maxLength={4000} onChange={(event) => { setComment(event.target.value); clearMessages(); }} rows={2} value={comment} /></label>
          </div>

          {error ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
          {confirmClose ? <div className="patient-close-warning" role="alert"><span><strong>Є незбережені дані запису</strong><small>Відкинути їх і закрити форму?</small></span><div><button className="button button--secondary" onClick={() => { setConfirmClose(false); }} type="button">Продовжити</button><button className="button button--danger" onClick={onClose} type="button">Відкинути</button></div></div> : null}
          <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button><button className="button button--primary" disabled={isSaving || isLoadingServices || isLoadingPresetPatient} type="submit">{isSaving ? "Створюємо…" : "Створити запис"}</button></div>
        </form>
      </section>
      {isCreatingPatient ? <PatientCreateDialog onClose={() => { setIsCreatingPatient(false); }} onSaved={(patient) => { setSelectedPatient(patientReference(patient)); setIsCreatingPatient(false); setPatientSearch(""); setPatientResults([]); clearMessages(); }} /> : null}
    </div>
  );
}

export type { SlotPreset };
