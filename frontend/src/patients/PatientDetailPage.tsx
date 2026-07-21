import { useCallback, useEffect, useMemo, useState, type SyntheticEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";
import { WorkItemCreateDialog } from "../work-items/WorkItemCreateDialog";

type PatientDetail = components["schemas"]["PatientDetailResponse"];
type MedicalPatientDetail = components["schemas"]["MedicalPatientDetail"];
type MedicalUpdate = components["schemas"]["PatchedMedicalPatientUpdateRequest"];
type FieldErrors = Record<string, readonly string[]>;
type PatientTab = "overview" | "visits" | "photos";

interface EditFormState {
  readonly firstName: string;
  readonly lastName: string;
  readonly phone: string;
  readonly birthDate: string;
  readonly email: string;
  readonly note: string;
  readonly allergies: string;
  readonly chronicConditions: string;
  readonly medicalNotes: string;
}

function initials(displayName: string): string {
  return displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "Не вказано";
  }
  return new Intl.DateTimeFormat("uk-UA", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}

function formatMedicalList(items: readonly string[]): string {
  return items.join(", ");
}

function medicalItems(value: unknown): readonly string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function medicalNote(value: string | undefined): string {
  if (value === undefined || value.trim() === "") {
    return "Медичних нотаток ще немає.";
  }
  return value;
}

function parseMedicalList(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function isMedicalPatient(patient: PatientDetail): patient is MedicalPatientDetail {
  return "medical_profile" in patient;
}

function editFormFor(patient: PatientDetail): EditFormState {
  const medical = isMedicalPatient(patient) ? patient.medical_profile : null;
  return {
    firstName: patient.first_name,
    lastName: patient.last_name,
    phone: patient.phone,
    birthDate: patient.birth_date ?? "",
    email: patient.email ?? "",
    note: patient.note ?? "",
    allergies: medical ? formatMedicalList(medicalItems(medical.allergies)) : "",
    chronicConditions: medical ? formatMedicalList(medicalItems(medical.chronic_conditions)) : "",
    medicalNotes: medical?.notes ?? "",
  };
}

function fieldMessage(errors: FieldErrors, field: string): string | null {
  return errors[field]?.[0] ?? null;
}

function PatientEditDialog({
  patient,
  onClose,
  onSaved,
}: {
  readonly patient: PatientDetail;
  readonly onClose: () => void;
  readonly onSaved: (patient: PatientDetail) => void;
}) {
  const initialForm = useMemo(() => editFormFor(patient), [patient]);
  const [form, setForm] = useState<EditFormState>(initialForm);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [confirmClose, setConfirmClose] = useState(false);
  const medical = isMedicalPatient(patient);
  const isDirty = JSON.stringify(form) !== JSON.stringify(initialForm);

  const update = <Key extends keyof EditFormState>(key: Key, value: EditFormState[Key]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setError(null);
    setFieldErrors({});
    setConfirmClose(false);
  };

  const requestClose = () => {
    if (isDirty) {
      setConfirmClose(true);
      return;
    }
    onClose();
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setFieldErrors({});
    const body: MedicalUpdate = {
      first_name: form.firstName,
      last_name: form.lastName,
      phone: form.phone,
      birth_date: form.birthDate || null,
      email: form.email,
      note: form.note,
    };
    if (medical) {
      body.medical_profile = {
        allergies: parseMedicalList(form.allergies),
        chronic_conditions: parseMedicalList(form.chronicConditions),
        notes: form.medicalNotes,
      };
    }
    const result = await apiClient.PATCH("/api/v1/patients/{patient_id}", {
      params: { path: { patient_id: patient.id } },
      headers: csrfHeaders(),
      body,
    });
    setIsSaving(false);
    if (result.error) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
      return;
    }
    onSaved(result.data);
  };

  return (
    <div className="modal-layer" role="presentation">
      <section aria-labelledby="patient-edit-title" aria-modal="true" className="modal-card patient-edit" role="dialog">
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Картка пацієнта · TP-302</p>
            <h2 id="patient-edit-title">Редагувати дані</h2>
            <p>Зміни збережуться в журналі дій.</p>
          </div>
          <button aria-label="Закрити редагування" className="icon-button" onClick={requestClose} type="button"><Icon name="close" /></button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="modal-card__body patient-form-grid">
            <label className="form-field"><span>Ім’я</span><input aria-invalid={Boolean(fieldMessage(fieldErrors, "first_name"))} onChange={(event) => { update("firstName", event.target.value); }} value={form.firstName} />{fieldMessage(fieldErrors, "first_name") ? <small className="field-error">{fieldMessage(fieldErrors, "first_name")}</small> : null}</label>
            <label className="form-field"><span>Прізвище</span><input aria-invalid={Boolean(fieldMessage(fieldErrors, "last_name"))} onChange={(event) => { update("lastName", event.target.value); }} value={form.lastName} />{fieldMessage(fieldErrors, "last_name") ? <small className="field-error">{fieldMessage(fieldErrors, "last_name")}</small> : null}</label>
            <label className="form-field"><span>Телефон</span><input aria-invalid={Boolean(fieldMessage(fieldErrors, "phone"))} onChange={(event) => { update("phone", event.target.value); }} value={form.phone} />{fieldMessage(fieldErrors, "phone") ? <small className="field-error">{fieldMessage(fieldErrors, "phone")}</small> : null}</label>
            <label className="form-field"><span>Дата народження</span><input max={new Date().toISOString().slice(0, 10)} onChange={(event) => { update("birthDate", event.target.value); }} type="date" value={form.birthDate} />{fieldMessage(fieldErrors, "birth_date") ? <small className="field-error">{fieldMessage(fieldErrors, "birth_date")}</small> : null}</label>
            <label className="form-field patient-form-wide"><span>Email</span><input onChange={(event) => { update("email", event.target.value); }} type="email" value={form.email} /></label>
            <label className="form-field patient-form-wide"><span>Адміністративна нотатка</span><textarea onChange={(event) => { update("note", event.target.value); }} rows={2} value={form.note} /></label>
            {medical ? (
              <fieldset className="patient-medical-editor patient-form-wide">
                <legend>Медична інформація</legend>
                <p>Ці поля сервер повертає лише адміну та подологу з доступом до пацієнта.</p>
                <label className="form-field"><span>Алергії</span><textarea onChange={(event) => { update("allergies", event.target.value); }} placeholder="Через кому" rows={2} value={form.allergies} /></label>
                <label className="form-field"><span>Хронічні стани</span><textarea onChange={(event) => { update("chronicConditions", event.target.value); }} placeholder="Через кому" rows={2} value={form.chronicConditions} /></label>
                <label className="form-field patient-form-wide"><span>Медична нотатка</span><textarea onChange={(event) => { update("medicalNotes", event.target.value); }} rows={3} value={form.medicalNotes} /></label>
              </fieldset>
            ) : null}
            {error ? <div className="form-error patient-form-wide" role="alert"><Icon name="warning" />{error}</div> : null}
            {confirmClose ? (
              <div className="patient-close-warning patient-form-wide" role="alert">
                <span><strong>Є незбережені зміни</strong><small>Відкинути їх і закрити форму?</small></span>
                <div><button className="button button--secondary" onClick={() => { setConfirmClose(false); }} type="button">Продовжити</button><button className="button button--danger" onClick={onClose} type="button">Відкинути</button></div>
              </div>
            ) : null}
          </div>
          <footer className="modal-card__footer"><button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button><button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Зберігаємо…" : "Зберегти зміни"}</button></footer>
        </form>
      </section>
    </div>
  );
}

function OverviewTab({ patient }: { readonly patient: PatientDetail }) {
  const medicalPatient = isMedicalPatient(patient) ? patient : null;
  const allergies = medicalPatient ? medicalItems(medicalPatient.medical_profile.allergies) : [];
  const chronicConditions = medicalPatient
    ? medicalItems(medicalPatient.medical_profile.chronic_conditions)
    : [];
  return (
    <div className="patient-detail-grid">
      <section className="surface patient-next-visit" aria-labelledby="next-visit-title">
        <header><div><p className="eyebrow">Найближчий запис</p><h2 id="next-visit-title">Записів ще немає</h2></div><span className="patient-state">Новий пацієнт</span></header>
        <div className="patient-shell-empty"><Icon name="calendar" /><div><strong>Календар підключиться у TP-401</strong><p>Картка вже готова бути locked-контекстом для нового запису.</p></div></div>
      </section>
      {medicalPatient ? (
        <section className="surface patient-medical-summary" aria-labelledby="medical-summary-title">
          <header><div><p className="eyebrow">Доступ: медичний</p><h2 id="medical-summary-title">Коротка медична інформація</h2></div><Icon name="lock" /></header>
          <dl>
            <div><dt>Алергії</dt><dd>{allergies.length ? allergies.join(", ") : "Не зазначено"}</dd></div>
            <div><dt>Хронічні стани</dt><dd>{chronicConditions.length ? chronicConditions.join(", ") : "Не зазначено"}</dd></div>
          </dl>
          <div className="patient-medical-note"><span>Остання нотатка подолога</span><p>{medicalNote(medicalPatient.medical_profile.notes)}</p></div>
        </section>
      ) : (
        <section className="surface patient-access-explainer" aria-labelledby="limited-access-title">
          <Icon name="lock" />
          <div><p className="eyebrow">Reception-safe projection</p><h2 id="limited-access-title">Медичні блоки мають обмежений доступ</h2><p>Сервер не передає медичний профіль і фото для ролі ресепшну. Контактні та організаційні дані залишаються доступними.</p></div>
        </section>
      )}
      <section className="surface patient-history-preview" aria-labelledby="history-preview-title">
        <header><div><p className="eyebrow">Коротка історія</p><h2 id="history-preview-title">Візитів ще немає</h2></div></header>
        <div className="patient-shell-empty"><Icon name="empty" /><div><strong>Історія з’явиться після завершення прийому</strong><p>Role-safe visit projection буде підключена у TP-601/TP-605.</p></div></div>
      </section>
    </div>
  );
}

function HistoryTab() {
  return (
    <section className="surface patient-tab-shell" aria-labelledby="patient-history-title">
      <div className="patient-shell-empty patient-shell-empty--large"><Icon name="calendar" /><div><h2 id="patient-history-title">Історія візитів порожня</h2><p>Тут хронологічно відображатимуться дата, статус, послуги, спеціаліст, вартість і безпечний для ролі підсумок.</p></div></div>
    </section>
  );
}

function PhotosTab() {
  return (
    <section className="surface patient-tab-shell" aria-labelledby="patient-photos-title">
      <div className="patient-shell-empty patient-shell-empty--large"><Icon name="empty" /><div><h2 id="patient-photos-title">Архів фото порожній</h2><p>Фото «до / після» будуть згруповані за відвідуваннями після підключення приватного lifecycle у TP-603.</p></div></div>
    </section>
  );
}

export function PatientDetailPage() {
  const { patientId = "", tab: requestedTab = "overview" } = useParams();
  const navigate = useNavigate();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreatingCallback, setIsCreatingCallback] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  const loadPatient = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setNotFound(false);
    const result = await apiClient.GET("/api/v1/patients/{patient_id}", {
      params: { path: { patient_id: patientId } },
    });
    setIsLoading(false);
    if (result.error) {
      setNotFound(result.response.status === 404);
      setError(result.error.message);
      return;
    }
    setPatient(result.data);
  }, [patientId]);

  useEffect(() => {
    void loadPatient();
  }, [loadPatient]);

  if (isLoading) {
    return <section aria-busy="true" className="surface patient-detail-loading"><span /><span /><span /></section>;
  }
  if (patient === null) {
    return (
      <section className="surface patient-detail-error">
        <span className="patient-empty__icon"><Icon name={notFound ? "lock" : "warning"} /></span>
        <h1>{notFound ? "Картку пацієнта не знайдено" : "Не вдалося завантажити картку"}</h1>
        <p>{notFound ? "Пацієнт не існує або недоступний у межах вашої ролі." : error}</p>
        <div><Link className="button button--secondary" to="/patients">До каталогу</Link>{notFound ? null : <button className="button button--primary" onClick={() => void loadPatient()} type="button">Повторити</button>}</div>
      </section>
    );
  }

  const medical = isMedicalPatient(patient);
  const allowedTabs: readonly PatientTab[] = medical ? ["overview", "visits", "photos"] : ["overview", "visits"];
  const tab = allowedTabs.includes(requestedTab as PatientTab) ? requestedTab as PatientTab : "overview";
  const tabItems: readonly { readonly id: PatientTab; readonly label: string }[] = medical
    ? [{ id: "overview", label: "Огляд" }, { id: "visits", label: "Історія візитів" }, { id: "photos", label: "Фото до / після" }]
    : [{ id: "overview", label: "Огляд" }, { id: "visits", label: "Історія візитів" }];

  return (
    <>
      <Link className="patient-back-link" to="/patients"><Icon name="arrow-left" />До каталогу пацієнтів</Link>
      {success ? <div className="success-banner" role="status"><Icon name="patients" /><span>{success}</span></div> : null}
      <section className="surface patient-card-header">
        <div className="patient-card-header__identity"><span className="avatar avatar--lilac">{initials(patient.display_name)}</span><div><p className="eyebrow">Картка пацієнта · {medical ? "медичний доступ" : "reception-safe"}</p><h1>{patient.display_name}</h1><span>{patient.public_number} · {patient.age === null ? "Вік не вказано" : `${String(patient.age)} років`}</span></div></div>
        <div className="patient-card-header__actions"><Link className="button button--primary" to={`/calendar?compose=appointment&patient=${patient.id}`}><Icon name="plus" />Записати</Link><button className="button button--secondary" onClick={() => { setIsCreatingCallback(true); }} type="button"><Icon name="phone" />Перетелефонувати</button><button className="button button--secondary" onClick={() => { setIsEditing(true); }} type="button">Редагувати</button></div>
        <dl className="patient-card-facts">
          <div><dt>Телефон</dt><dd>{patient.phone}</dd></div>
          <div><dt>Email</dt><dd>{patient.email === undefined || patient.email === "" ? "Не вказано" : patient.email}</dd></div>
          <div><dt>Дата народження</dt><dd>{formatDate(patient.birth_date)}</dd></div>
          <div><dt>Обслуговується з</dt><dd>{formatDate(patient.service_started_at)}</dd></div>
          <div><dt>Основний подолог</dt><dd>{patient.primary_podologist?.display_name ?? "Не призначено"}</dd></div>
        </dl>
      </section>
      <nav aria-label="Розділи картки пацієнта" className="patient-detail-tabs">
        {tabItems.map((item) => <button aria-current={tab === item.id ? "page" : undefined} className={tab === item.id ? "active" : ""} key={item.id} onClick={() => { void navigate(`/patients/${patient.id}/${item.id}`); }} type="button">{item.label}</button>)}
      </nav>
      {tab === "overview" ? <OverviewTab patient={patient} /> : null}
      {tab === "visits" ? <HistoryTab /> : null}
      {tab === "photos" && medical ? <PhotosTab /> : null}
      {isEditing ? <PatientEditDialog patient={patient} onClose={() => { setIsEditing(false); }} onSaved={(updated) => { setPatient(updated); setIsEditing(false); setSuccess("Зміни картки пацієнта збережено й зафіксовано в журналі дій."); }} /> : null}
      {isCreatingCallback ? <WorkItemCreateDialog initialKind="callback" onClose={() => { setIsCreatingCallback(false); }} onSaved={(item) => { setIsCreatingCallback(false); setSuccess(`Справу «${item.title}» створено. Автоматичний дзвінок не виконувався.`); }} presetPatient={{ id: patient.id, public_number: patient.public_number, display_name: patient.display_name, phone: patient.phone }} /> : null}
    </>
  );
}
