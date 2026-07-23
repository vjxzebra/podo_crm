import { useEffect, useMemo, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders, useAuth } from "../auth/AuthContext";

type WorkItem = components["schemas"]["WorkItem"];
type WorkItemAssignee = components["schemas"]["WorkItemAssignee"];
type WorkItemKind = components["schemas"]["WorkItemKindEnum"];
type WorkItemPatient = components["schemas"]["WorkItemPatient"];
type WorkItemCreateRequest = components["schemas"]["WorkItemCreateRequest"];
type Patient = components["schemas"]["PatientListItem"];
type FieldErrors = Record<string, readonly string[]>;

interface WorkItemCreateDialogProps {
  readonly assignees?: readonly WorkItemAssignee[];
  readonly initialKind?: WorkItemKind;
  readonly onClose: () => void;
  readonly onSaved: (item: WorkItem) => void;
  readonly presetPatient?: WorkItemPatient;
}

const kindOptions: readonly { readonly value: WorkItemKind; readonly label: string }[] = [
  { value: "callback", label: "Перетелефонувати" },
  { value: "confirm_appointment", label: "Підтвердити запис" },
  { value: "manual_message", label: "Написати пацієнту вручну" },
  { value: "other", label: "Інша внутрішня справа" },
];

function dueDefaults(): { readonly date: string; readonly time: string } {
  const value = new Date(Date.now() + 60 * 60 * 1000);
  value.setMinutes(0, 0, 0);
  const year = String(value.getFullYear());
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hours = String(value.getHours()).padStart(2, "0");
  return { date: `${year}-${month}-${day}`, time: `${hours}:00` };
}

function patientReference(patient: Patient): WorkItemPatient {
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

export function WorkItemCreateDialog({
  assignees: suppliedAssignees,
  initialKind = "other",
  onClose,
  onSaved,
  presetPatient,
}: WorkItemCreateDialogProps) {
  const { state } = useAuth();
  const [initialDue] = useState(dueDefaults);
  const defaultTitle = initialKind === "callback" && presetPatient
    ? `Перетелефонувати: ${presetPatient.display_name}`
    : "";
  const currentUserId = state.status === "authenticated" ? String(state.session.user.id) : "";
  const [kind, setKind] = useState<WorkItemKind>(initialKind);
  const [title, setTitle] = useState(defaultTitle);
  const [dueDate, setDueDate] = useState(initialDue.date);
  const [dueTime, setDueTime] = useState(initialDue.time);
  const [assigneeId, setAssigneeId] = useState(currentUserId);
  const [comment, setComment] = useState("");
  const [isImportant, setIsImportant] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState<WorkItemPatient | null>(presetPatient ?? null);
  const [patientSearch, setPatientSearch] = useState("");
  const [patientResults, setPatientResults] = useState<readonly Patient[]>([]);
  const [isSearchingPatients, setIsSearchingPatients] = useState(false);
  const [remoteAssignees, setRemoteAssignees] = useState<readonly WorkItemAssignee[]>([]);
  const [isLoadingAssignees, setIsLoadingAssignees] = useState(suppliedAssignees === undefined);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [confirmClose, setConfirmClose] = useState(false);
  const assignees = suppliedAssignees ?? remoteAssignees;
  const initialFingerprint = useMemo(() => JSON.stringify({
    kind: initialKind,
    title: defaultTitle,
    dueDate: initialDue.date,
    dueTime: initialDue.time,
    assigneeId: currentUserId,
    comment: "",
    isImportant: false,
    patientId: presetPatient?.id ?? null,
  }), [currentUserId, defaultTitle, initialDue.date, initialDue.time, initialKind, presetPatient?.id]);
  const fingerprint = JSON.stringify({
    kind,
    title,
    dueDate,
    dueTime,
    assigneeId,
    comment,
    isImportant,
    patientId: selectedPatient?.id ?? null,
  });

  useEffect(() => {
    if (suppliedAssignees !== undefined) {
      return;
    }
    const loadAssignees = async () => {
      const result = await apiClient.GET("/api/v1/work-items", {
        params: { query: { scope: "own", status: "open" } },
      }).catch(() => null);
      setIsLoadingAssignees(false);
      if (result?.data === undefined) {
        setError(result?.error.message ?? "Не вдалося завантажити працівників.");
        return;
      }
      setRemoteAssignees(result.data.assignees);
    };
    void loadAssignees();
  }, [suppliedAssignees]);

  useEffect(() => {
    if (presetPatient || patientSearch.trim().length < 2) {
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
  }, [patientSearch, presetPatient]);

  const update = () => {
    setError(null);
    setFieldErrors({});
    setConfirmClose(false);
  };

  const requestClose = () => {
    if (fingerprint !== initialFingerprint) {
      setConfirmClose(true);
      return;
    }
    onClose();
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    const dueAt = new Date(`${dueDate}T${dueTime}:00`);
    if (Number.isNaN(dueAt.getTime())) {
      setFieldErrors({ due_at: ["Укажіть коректні дату й час."] });
      return;
    }
    const parsedAssigneeId = Number(assigneeId);
    if (!Number.isInteger(parsedAssigneeId) || parsedAssigneeId < 1) {
      setFieldErrors({ assignee_id: ["Оберіть відповідального."] });
      return;
    }
    setIsSaving(true);
    setError(null);
    setFieldErrors({});
    const body: WorkItemCreateRequest = {
      kind,
      title,
      due_at: dueAt.toISOString(),
      assignee_id: parsedAssigneeId,
      patient_id: selectedPatient?.id ?? null,
      comment,
      is_important: isImportant,
    };
    const result = await apiClient.POST("/api/v1/work-items", {
      body,
      headers: csrfHeaders(),
    }).catch(() => null);
    setIsSaving(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
      return;
    }
    if (result.data === undefined) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
      return;
    }
    onSaved(result.data);
  };

  return (
    <div className="modal-layer" role="presentation">
      <section aria-labelledby="work-item-create-title" aria-modal="true" className="modal-card work-item-editor" role="dialog">
        <header className="modal-card__header">
          <div><p className="eyebrow">Внутрішня справа · TP-303</p><h2 id="work-item-create-title">Нова справа</h2><p>Задайте відповідального й точний строк виконання.</p></div>
          <button aria-label="Закрити форму справи" className="icon-button" onClick={requestClose} type="button"><Icon name="close" /></button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="work-item-form-grid">
            <label className="form-field"><span>Тип справи</span><select onChange={(event) => { setKind(event.target.value as WorkItemKind); update(); }} value={kind}>{kindOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label className="form-field"><span>Відповідальний</span><select disabled={isLoadingAssignees} onChange={(event) => { setAssigneeId(event.target.value); update(); }} value={assigneeId}><option value="">Оберіть працівника</option>{assignees.map((assignee) => <option key={assignee.id} value={assignee.id}>{assignee.display_name}</option>)}</select>{fieldMessage(fieldErrors, "assignee_id") ? <small className="field-error">{fieldMessage(fieldErrors, "assignee_id")}</small> : null}</label>
            <label className="form-field work-item-form-wide"><span>Назва</span><input maxLength={200} onChange={(event) => { setTitle(event.target.value); update(); }} required value={title} />{fieldMessage(fieldErrors, "title") ? <small className="field-error">{fieldMessage(fieldErrors, "title")}</small> : null}</label>
            <label className="form-field"><span>Дата</span><input onChange={(event) => { setDueDate(event.target.value); update(); }} required type="date" value={dueDate} /></label>
            <label className="form-field"><span>Час</span><input onChange={(event) => { setDueTime(event.target.value); update(); }} required type="time" value={dueTime} />{fieldMessage(fieldErrors, "due_at") ? <small className="field-error">{fieldMessage(fieldErrors, "due_at")}</small> : null}</label>
            <div className="work-item-form-wide work-item-patient-field">
              <span>Пацієнт {kind === "callback" ? "· обов’язково" : "· необов’язково"}</span>
              {selectedPatient ? <div className="work-item-selected-patient"><span><strong>{selectedPatient.display_name}</strong><small>{selectedPatient.public_number} · {selectedPatient.phone}</small></span>{presetPatient ? <Icon name="lock" /> : <button aria-label="Відв’язати пацієнта" className="text-action" onClick={() => { setSelectedPatient(null); update(); }} type="button">Змінити</button>}</div> : <><label className="patient-search"><Icon name="search" /><span className="visually-hidden">Знайти пацієнта для справи</span><input onChange={(event) => { setPatientSearch(event.target.value); update(); }} placeholder="Ім’я, телефон або № пацієнта" type="search" value={patientSearch} /></label>{isSearchingPatients ? <small>Шукаємо пацієнта…</small> : null}{patientResults.length ? <div className="work-item-patient-results">{patientResults.map((patient) => <button key={patient.id} onClick={() => { setSelectedPatient(patientReference(patient)); setPatientSearch(""); setPatientResults([]); update(); }} type="button"><strong>{patient.display_name}</strong><small>{patient.public_number} · {patient.phone}</small></button>)}</div> : null}</>}
              {fieldMessage(fieldErrors, "patient_id") ? <small className="field-error">{fieldMessage(fieldErrors, "patient_id")}</small> : null}
            </div>
            <label className="form-field work-item-form-wide"><span>Коментар · необов’язково</span><textarea maxLength={4000} onChange={(event) => { setComment(event.target.value); update(); }} rows={3} value={comment} /></label>
            <label className="settings-check work-item-form-wide"><input checked={isImportant} onChange={(event) => { setIsImportant(event.target.checked); update(); }} type="checkbox" /><span><strong>Важлива справа</strong><small>Буде виділена у списку й підсумку.</small></span></label>
          </div>
          {error ? <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div> : null}
          {confirmClose ? <div className="patient-close-warning" role="alert"><span><strong>Є незбережені зміни</strong><small>Відкинути їх і закрити форму?</small></span><div><button className="button button--secondary" onClick={() => { setConfirmClose(false); }} type="button">Продовжити</button><button className="button button--danger" onClick={onClose} type="button">Відкинути</button></div></div> : null}
          <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button><button className="button button--primary" disabled={isSaving || isLoadingAssignees} type="submit">{isSaving ? "Створюємо…" : "Створити справу"}</button></div>
        </form>
      </section>
    </div>
  );
}
