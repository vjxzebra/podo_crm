import { useCallback, useEffect, useState, type SyntheticEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders, roleLabels, useAuth } from "../auth/AuthContext";

type Patient = components["schemas"]["PatientListItem"];
type CreatedPatient = components["schemas"]["Patient"];
type FieldErrors = Readonly<Record<string, readonly string[]>>;

interface PatientFormState {
  readonly firstName: string;
  readonly lastName: string;
  readonly phone: string;
  readonly birthDate: string;
  readonly email: string;
  readonly note: string;
}

const emptyForm: PatientFormState = {
  firstName: "",
  lastName: "",
  phone: "",
  birthDate: "",
  email: "",
  note: "",
};

function initials(displayName: string): string {
  return displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toLocaleUpperCase("uk");
}

function fieldMessage(errors: FieldErrors, field: string): string | null {
  return errors[field]?.[0] ?? null;
}

export function PatientCreateDialog({
  onClose,
  onSaved,
}: {
  readonly onClose: () => void;
  readonly onSaved: (patient: CreatedPatient, duplicateWarning: boolean) => void;
}) {
  const { state } = useAuth();
  const [form, setForm] = useState<PatientFormState>(emptyForm);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [possibleDuplicates, setPossibleDuplicates] = useState<readonly Patient[]>([]);
  const [isCheckingPhone, setIsCheckingPhone] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const isDirty = form.firstName.trim() !== ""
    || form.lastName.trim() !== ""
    || form.phone.trim() !== ""
    || form.birthDate.trim() !== ""
    || form.email.trim() !== ""
    || form.note.trim() !== "";

  const update = <Key extends keyof PatientFormState>(
    key: Key,
    value: PatientFormState[Key],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
    setConfirmClose(false);
  };

  const requestClose = () => {
    if (isDirty) {
      setConfirmClose(true);
    } else {
      onClose();
    }
  };

  useEffect(() => {
    const digitCount = form.phone.replace(/\D/g, "").length;
    if (digitCount < 7) {
      setPossibleDuplicates([]);
      setIsCheckingPhone(false);
      return;
    }
    let active = true;
    setIsCheckingPhone(true);
    const timeout = window.setTimeout(() => {
      void apiClient.GET("/api/v1/patients", {
        params: { query: { search: form.phone } },
      }).then((result) => {
        if (active) {
          setPossibleDuplicates(result.data?.patients ?? []);
          setIsCheckingPhone(false);
        }
      }).catch(() => {
        if (active) {
          setPossibleDuplicates([]);
          setIsCheckingPhone(false);
        }
      });
    }, 350);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [form.phone]);

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setFieldErrors({});
    const result = await apiClient.POST("/api/v1/patients", {
      body: {
        first_name: form.firstName,
        last_name: form.lastName,
        phone: form.phone,
        ...(form.birthDate ? { birth_date: form.birthDate } : {}),
        ...(form.email ? { email: form.email } : {}),
        ...(form.note ? { note: form.note } : {}),
      },
      headers: csrfHeaders(),
    }).catch(() => null);

    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
    } else {
      onSaved(result.data.patient, result.data.duplicate_warning);
    }
    setIsSaving(false);
  };

  const role = state.status === "authenticated" ? state.session.user.role : "reception";

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="patient-create-title">
      <form className="modal-card patient-create" onSubmit={(event) => void submit(event)}>
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Пацієнти · TP-301</p>
            <h2 id="patient-create-title">Новий пацієнт</h2>
          </div>
          <button className="icon-button" onClick={requestClose} type="button" aria-label="Закрити форму пацієнта">
            <Icon name="close" />
          </button>
        </header>
        <p className="modal-intro">
          Ім’я, прізвище й телефон обов’язкові. Подібний телефон покаже попередження, але не заблокує створення.
        </p>

        {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
        {role === "podologist" ? (
          <div className="patient-scope-note"><Icon name="lock" /><span><strong>Пацієнт буде призначений вам</strong><small>У каталозі подолога відображаються лише власні пацієнти.</small></span></div>
        ) : null}

        <div className="patient-form-grid">
          <label className="form-field"><span>Ім’я</span><input autoComplete="given-name" autoFocus maxLength={100} onChange={(event) => { update("firstName", event.target.value); }} required value={form.firstName} />{fieldMessage(fieldErrors, "first_name") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "first_name")}</small>}</label>
          <label className="form-field"><span>Прізвище</span><input autoComplete="family-name" maxLength={100} onChange={(event) => { update("lastName", event.target.value); }} required value={form.lastName} />{fieldMessage(fieldErrors, "last_name") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "last_name")}</small>}</label>
          <label className="form-field"><span>Телефон</span><input autoComplete="tel" inputMode="tel" maxLength={32} onChange={(event) => { update("phone", event.target.value); }} placeholder="+380 67 123 45 67" required value={form.phone} />{fieldMessage(fieldErrors, "phone") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "phone")}</small>}</label>
          <label className="form-field"><span>Дата народження</span><input max={new Date().toISOString().slice(0, 10)} onChange={(event) => { update("birthDate", event.target.value); }} type="date" value={form.birthDate} />{fieldMessage(fieldErrors, "birth_date") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "birth_date")}</small>}</label>
          <label className="form-field patient-form-wide"><span>Email · необов’язково</span><input autoComplete="email" maxLength={254} onChange={(event) => { update("email", event.target.value); }} type="email" value={form.email} />{fieldMessage(fieldErrors, "email") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "email")}</small>}</label>
          <label className="form-field patient-form-wide"><span>Примітка · необов’язково</span><textarea maxLength={2000} onChange={(event) => { update("note", event.target.value); }} rows={3} value={form.note} />{fieldMessage(fieldErrors, "note") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "note")}</small>}</label>
        </div>

        {isCheckingPhone ? <p className="patient-duplicate-check" role="status">Перевіряємо можливі дублікати…</p> : null}
        {possibleDuplicates.length === 0 ? null : (
          <section className="patient-duplicate-warning" aria-labelledby="duplicate-warning-title">
            <Icon name="warning" />
            <div>
              <strong id="duplicate-warning-title">Можливий дублікат телефону</strong>
              <p>Перевірте збіги. За потреби нового пацієнта все одно можна створити.</p>
              <ul>{possibleDuplicates.slice(0, 3).map((patient) => <li key={patient.id}><span>{patient.display_name}</span><small>{patient.public_number} · {patient.phone}</small></li>)}</ul>
            </div>
          </section>
        )}

        {confirmClose ? (
          <div className="patient-close-warning" role="alert">
            <span><strong>Відкинути введені дані?</strong><small>Незбережені поля буде втрачено.</small></span>
            <div><button className="button button--secondary" onClick={() => { setConfirmClose(false); }} type="button">Продовжити</button><button className="button button--danger" onClick={onClose} type="button">Відкинути</button></div>
          </div>
        ) : null}

        <div className="modal-actions">
          <button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button>
          <button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Створюємо…" : "Створити пацієнта"}</button>
        </div>
      </form>
    </div>
  );
}

export function PatientsPage() {
  const { state } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [patients, setPatients] = useState<readonly Patient[]>([]);
  const [search, setSearch] = useState("");
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const isCreating = searchParams.get("compose") === "patient";

  const openCreate = () => {
    const next = new URLSearchParams(searchParams);
    next.set("compose", "patient");
    setSearchParams(next);
  };
  const closeCreate = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("compose");
    setSearchParams(next, { replace: true });
  };

  const loadPatients = useCallback(async (
    query: string,
    cursor: string | null,
    append: boolean,
  ) => {
    if (append) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
    }
    setError(null);
    const result = await apiClient.GET("/api/v1/patients", {
      params: {
        query: {
          ...(query.trim() ? { search: query.trim() } : {}),
          ...(cursor ? { cursor } : {}),
        },
      },
    }).catch(() => null);
    if (result === null) {
      setError("Не вдалося зв’язатися із сервером.");
    } else if (result.data === undefined) {
      setError(result.error.message);
    } else {
      setPatients((current) => append ? [...current, ...result.data.patients] : result.data.patients);
      setNextCursor(result.data.next_cursor);
    }
    setIsLoading(false);
    setIsLoadingMore(false);
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void loadPatients(search, null, false);
    }, search ? 250 : 0);
    return () => { window.clearTimeout(timeout); };
  }, [loadPatients, search]);

  const role = state.status === "authenticated" ? state.session.user.role : "reception";
  const scopeLabel = role === "podologist" ? "Лише мої пацієнти" : "Усі пацієнти кабінету";

  return (
    <>
      <header className="page-heading patients-heading">
        <div>
          <p className="eyebrow">Пацієнти · TP-301</p>
          <h1>Каталог пацієнтів</h1>
          <p>Пошук за ім’ям, прізвищем, телефоном або внутрішнім номером.</p>
        </div>
        <button className="button button--primary" onClick={openCreate} type="button"><Icon name="plus" />Додати пацієнта</button>
      </header>

      {success === null ? null : <div className="form-message form-message--success" role="status"><Icon name="patients" /><span>{success}</span></div>}

      <section className="patients-panel panel" aria-labelledby="patient-directory-title">
        <div className="patients-toolbar">
          <label className="patient-search">
            <span className="visually-hidden">Пошук пацієнтів</span>
            <Icon name="search" />
            <input onChange={(event) => { setSearch(event.target.value); setSuccess(null); }} placeholder="Ім’я, телефон або № пацієнта" type="search" value={search} />
          </label>
          <span className="patient-scope-pill"><Icon name="lock" />{scopeLabel}</span>
          <button className="icon-button" onClick={() => void loadPatients(search, null, false)} type="button" aria-label="Оновити список"><Icon name="refresh" /></button>
        </div>

        <header className="patient-directory-summary">
          <div><h2 id="patient-directory-title">Пацієнти</h2><span>{isLoading ? "Оновлення…" : `Показано: ${String(patients.length)}`}</span></div>
          <small>Доступ: {roleLabels[role]}</small>
        </header>

        {error === null ? null : <div className="patient-list-message patient-list-message--error" role="alert"><Icon name="warning" /><span><strong>Не вдалося завантажити пацієнтів</strong><small>{error}</small></span><button className="button button--secondary" onClick={() => void loadPatients(search, null, false)} type="button">Повторити</button></div>}

        {isLoading && patients.length === 0 ? <div className="patient-skeletons" aria-label="Завантаження пацієнтів"><span /><span /><span /></div> : null}

        {!isLoading && error === null && patients.length === 0 ? (
          <div className="patient-empty">
            <span className="patient-empty__icon"><Icon name={search ? "search" : "patients"} /></span>
            <h2>{search ? "Збігів не знайдено" : "Пацієнтів ще немає"}</h2>
            <p>{search ? `За запитом «${search}» немає доступних пацієнтів.` : "Створіть першу картку пацієнта для цього каталогу."}</p>
            <button className="button button--primary" onClick={openCreate} type="button"><Icon name="plus" />Створити пацієнта</button>
          </div>
        ) : null}

        {patients.length === 0 ? null : (
          <div className="patient-directory">
            <div className="patient-directory__head" aria-hidden="true"><span>Пацієнт</span><span>Контакт</span><span>Відповідальний</span><span>Запис</span><span>Стан</span></div>
            {patients.map((patient) => (
              <Link aria-label={`Відкрити картку ${patient.display_name}`} className="patient-row" key={patient.id} to={`/patients/${patient.id}/overview`}>
                <div className="patient-identity"><span className="avatar avatar--lilac" aria-hidden="true">{initials(patient.display_name)}</span><span><strong>{patient.display_name}</strong><small>{patient.public_number}</small></span></div>
                <div className="patient-contact" data-label="Контакт"><strong>{patient.phone}</strong><small>{patient.email === undefined || patient.email === "" ? "Email не вказано" : patient.email}</small></div>
                <div className="patient-owner" data-label="Відповідальний"><strong>{patient.primary_podologist?.display_name ?? "Не призначено"}</strong><small>{patient.primary_podologist ? "Основний подолог" : "Можна призначити пізніше"}</small></div>
                <div className="patient-appointment" data-label="Запис"><strong>Записів ще немає</strong><small>Створіть запис із картки пацієнта або календаря</small></div>
                <span className="patient-state">{patient.state_label}</span>
              </Link>
            ))}
          </div>
        )}

        {nextCursor === null ? null : <div className="patient-pagination"><span>Завантажено {patients.length} записів</span><button className="button button--secondary" disabled={isLoadingMore} onClick={() => void loadPatients(search, nextCursor, true)} type="button">{isLoadingMore ? "Завантажуємо…" : "Показати ще"}</button></div>}
      </section>

      {isCreating ? <PatientCreateDialog onClose={closeCreate} onSaved={(patient, duplicateWarning) => {
        closeCreate();
        setSearch("");
        setSuccess(duplicateWarning ? `${patient.display_name} створено. Система позначила можливий дублікат телефону.` : `${patient.display_name} додано до каталогу.`);
        void loadPatients("", null, false);
      }} /> : null}
    </>
  );
}
